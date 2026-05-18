from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from quart import Blueprint, current_app
from quart_rate_limiter import rate_limit

from modules.endpoints.website.about import render_about
from modules.endpoints.website.home import render_home
from modules.endpoints.website.stats import render_stats

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue


website_bp = Blueprint("website", __name__)


@website_bp.route("/", methods=["GET"])
@rate_limit(30, timedelta(minutes=1))
async def home() -> ResponseReturnValue:
    config_quart: dict = current_app.config_quart  # noqa
    return await render_home(config=config_quart)


@website_bp.route("/stats", methods=["GET"])
@rate_limit(30, timedelta(minutes=1))
async def stats() -> ResponseReturnValue:
    config_quart: dict = current_app.config_quart  # noqa
    return await render_stats(config=config_quart)


@website_bp.route("/about", methods=["GET"])
@rate_limit(30, timedelta(minutes=1))
async def about() -> ResponseReturnValue:
    config_quart: dict = current_app.config_quart  # noqa
    return await render_about(config=config_quart)
