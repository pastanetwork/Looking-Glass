from __future__ import annotations

from typing import TYPE_CHECKING

from quart import jsonify, request

from modules.utility.i18n import make_translator, negotiate_language
from modules.utility.middleware import get_client_ip
from modules.utility.speedtest_script import build_speedtest_script

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue

    from modules.services.speedtest_service import SpeedtestService
    from modules.services.turnstile_service import TurnstileService


async def cli_token_func(config: dict, file_id: str, turnstile_token: str) -> ResponseReturnValue:
    turnstile_service: TurnstileService = config["turnstile_service"]
    speedtest_service: SpeedtestService = config["speedtest_service"]
    client_ip = get_client_ip() or ""

    if not speedtest_service.enabled:
        return jsonify({"status": "Error", "status_code": 404, "detail": "err_generic"}), 404

    size = speedtest_service.resolve_size(file_id)
    if size is None:
        return jsonify({"status": "Error", "status_code": 404, "detail": "err_generic"}), 404

    if not await turnstile_service.verify(turnstile_token, client_ip):
        return jsonify({"status": "Error", "status_code": 403, "detail": "err_turnstile"}), 403

    token = await speedtest_service.mint_cli_token()
    if token is None:
        body = jsonify({"status": "Error", "status_code": 503, "detail": "err_busy"})
        body.headers["Retry-After"] = "60"
        return body, 503

    base = (config.get("public_url") or request.host_url).rstrip("/")
    download_url = f"{base}/api/v1/speedtest/cli/{file_id}?token={token}"
    script_url = f"{base}/api/v1/speedtest/cli/script/{file_id}?token={token}"

    lang = negotiate_language(
        config["translations"],
        config["default_language"],
        request.cookies.get("lg_lang"),
        request.headers.get("Accept-Language"),
    )
    t = make_translator(config["translations"], lang, config["default_language"])
    labels = {
        "live": t("speedtest_cli_live"),
        "avg": t("speedtest_cli_avg"),
        "volume": t("speedtest_volume"),
        "duration": t("speedtest_elapsed"),
        "unit": t("speedtest_cli_unit"),
    }

    return jsonify({
        "status": "Ok",
        "status_code": 200,
        "data": {
            "token": token,
            "commands": {
                "linux": f'curl -fsSL "{script_url}&os=linux&lang={lang}" | sh',
                "windows": f'irm "{script_url}&os=windows&lang={lang}" | iex',
            },
            "scripts": {
                "linux": build_speedtest_script("linux", download_url=download_url, total=size, **labels),
                "windows": build_speedtest_script("windows", download_url=download_url, total=size, **labels),
            },
            "expires_in": speedtest_service.cli_token_ttl,
        },
    }), 200
