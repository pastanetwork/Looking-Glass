from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from quart import Blueprint, current_app
from quart_rate_limiter import rate_limit

from modules.endpoints.internal.stats.stats_overview import stats_overview_func

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue

api_v1_stats_bp = Blueprint("api_v1_stats", __name__, url_prefix="/api/v1")


@api_v1_stats_bp.route("/stats", methods=["GET"])
@rate_limit(30, timedelta(minutes=1))
async def stats_get() -> ResponseReturnValue:
    config_quart: dict = current_app.config_quart  # noqa
    return await stats_overview_func(config=config_quart)
