from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

from quart import Quart, Response, request
from quart_cors import cors
from quart_minify import Minify
from quart_rate_limiter import RateLimiter

from modules.executors.registry import NodeRegistry
from modules.repositories.query_log_repo import QueryLogRepository
from modules.router.api.lookingglass import api_v1_lg_bp
from modules.router.api.meta import api_v1_meta_bp
from modules.router.api.speedtest import api_v1_speedtest_bp
from modules.router.api.stats import api_v1_stats_bp
from modules.router.website.base import website_bp
from modules.router.website.errors import register_error_handlers
from modules.services.command_service import CommandService
from modules.services.concurrency_service import ConcurrencyService
from modules.services.speedtest_service import SpeedtestService
from modules.services.stats_service import StatsService
from modules.services.turnstile_service import TurnstileService
from modules.task.main import TaskMain
from modules.utility.cloudflare import fetch_cloudflare_nets
from modules.utility.config_loader import load_config
from modules.utility.database import get_db_connection, initialize_database
from modules.utility.i18n import load_translations, make_i18n_tag, make_translator, negotiate_language
from modules.utility.logging_setup import setup_logging
from modules.utility.masking import mask_target
from modules.utility.middleware import ProxyHeadersMiddleware, TrustedHostMiddleware, get_client_ip
from modules.utility.orjson_provider import OrjsonProvider
from modules.utility.redis_client import build_redis_store, create_redis_pool
from modules.utility.security_headers import apply_security_headers

if TYPE_CHECKING:
    import aiosqlite
    import redis.asyncio as redis


config_quart = load_config()

logger = setup_logging(config_quart["dev"])

config_quart["logger"] = logger
config_quart["translations"] = load_translations(logger)

app = Quart(__name__, static_folder=config_quart["static_folder"], static_url_path="/static")

_cors_cfg: dict = config_quart["cors"]
app.config["QUART_CORS_ALLOW_ORIGIN"] = _cors_cfg["allow_origin"]
app.config["QUART_CORS_ALLOW_CREDENTIALS"] = _cors_cfg["allow_credentials"]
app.config["QUART_CORS_ALLOW_METHODS"] = _cors_cfg["allow_methods"]
app.config["QUART_CORS_ALLOW_HEADERS"] = _cors_cfg["allow_headers"]
app.config["QUART_CORS_EXPOSE_HEADERS"] = _cors_cfg["expose_headers"]
app.config["QUART_CORS_MAX_AGE"] = _cors_cfg["max_age"]
app = cors(app)

app.json = OrjsonProvider(app)
Minify(app=app, js=False, cssless=False)

app.config["TEMPLATES_AUTO_RELOAD"] = config_quart["dev"]
app.config_quart = config_quart

rate_limiter = RateLimiter(app, store=build_redis_store(config_quart))

if not config_quart["dev"]:
    app.asgi_app = TrustedHostMiddleware(app.asgi_app, allowed_hosts=config_quart["allowed_hosts"])
    app.asgi_app = ProxyHeadersMiddleware(app.asgi_app, config_quart)

app.register_blueprint(api_v1_meta_bp)
app.register_blueprint(api_v1_lg_bp)
app.register_blueprint(api_v1_stats_bp)
app.register_blueprint(api_v1_speedtest_bp)
app.register_blueprint(website_bp)
register_error_handlers(app)


@app.context_processor
async def _inject_i18n() -> dict:
    """Injecte les helpers de traduction et de thème dans tous les templates."""
    translations = config_quart["translations"]
    default = config_quart["default_language"]
    lang = negotiate_language(
        translations,
        default,
        request.cookies.get("lg_lang"),
        request.headers.get("Accept-Language"),
    )
    translator = make_translator(translations, lang, default)
    return {
        "t": translator,
        "i18n": make_i18n_tag(translator),
        "lang": lang,
        "all_translations": translations,
        "available_languages": config_quart["i18n"]["available"],
        "static_folder": config_quart["static_folder"],
        "public_url": config_quart["public_url"],
    }


@app.before_serving
async def startup() -> None:
    db = await get_db_connection(config_quart["db_path"])
    await initialize_database(db, logger)
    config_quart["db"] = db

    config_quart["redis_pool"] = create_redis_pool(config_quart)

    config_quart["node_registry"] = NodeRegistry(config_quart["nodes"], config_quart["limits"], logger)

    query_log_repo = QueryLogRepository(db, logger)
    config_quart["query_log_repo"] = query_log_repo

    concurrency_service = ConcurrencyService(config_quart["redis_pool"], config_quart, logger)
    turnstile_service = TurnstileService(config_quart, logger)
    config_quart["turnstile_service"] = turnstile_service
    config_quart["command_service"] = CommandService(
        config_quart,
        config_quart["node_registry"],
        concurrency_service,turnstile_service,
        query_log_repo,
        logger
    )

    config_quart["stats_service"] = StatsService(query_log_repo, logger)

    config_quart["speedtest_service"] = SpeedtestService(
        config_quart["redis_pool"], config_quart, query_log_repo, logger
    )

    if config_quart["cloudflare"]["enabled"]:
        fetched = await fetch_cloudflare_nets(logger)
        if fetched:
            config_quart["cloudflare_nets"] = fetched
            logger.info("Plages Cloudflare récupérées (%d entrées).", len(fetched))
        else:
            logger.warning("Plages Cloudflare indisponibles : repli sur la liste intégrée.")

    task_main = TaskMain(config=config_quart)
    config_quart["task_main"] = task_main
    await task_main.start()

    logger.info("Looking Glass démarré (dev=%s)", config_quart["dev"])


@app.after_serving
async def shutdown() -> None:
    task_main: Optional[TaskMain] = config_quart.get("task_main")
    if task_main:
        await task_main.stop()

    registry: Optional[NodeRegistry] = config_quart.get("node_registry")
    if registry:
        await registry.aclose_all()

    turnstile_service: Optional[TurnstileService] = config_quart.get("turnstile_service")
    if turnstile_service:
        await turnstile_service.aclose()

    redis_pool: Optional[redis.ConnectionPool] = config_quart.get("redis_pool")
    if redis_pool:
        await redis_pool.aclose()

    db: Optional[aiosqlite.Connection] = config_quart.get("db")
    if db:
        await db.close()

    logger.info("Looking Glass arrêté")


@app.before_request
async def _log_start() -> None:
    """Enregistre l'heure de début de la requête pour mesurer la durée."""
    request._start_time = time.perf_counter()


@app.after_request
async def _after_request(response: Response) -> Response:
    """Pose les en-têtes de sécurité et journalise la requête."""
    apply_security_headers(response)
    _log_request(response)

    return response


def _log_request(response: Response) -> None:
    """Journalise la requête HTTP en excluant les assets statiques."""
    path = request.path
    if request.method == "GET" and (path.startswith("/static") or path == "/favicon.ico"):
        return

    start: Optional[float] = getattr(request, "_start_time", None)
    duration = (time.perf_counter() - start) * 1000 if start else 0.0
    ip = mask_target(get_client_ip(return_unknown=True) or "Unknown")

    logger.info("%s %s %s %s %.1fms", ip, request.method, path, response.status_code, duration)


if __name__ == "__main__":
    import asyncio

    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    hc = Config()
    hc.bind = [f"127.0.0.1:{config_quart['port']}"]
    hc.use_reloader = config_quart["dev"]
    asyncio.run(serve(app, hc))
