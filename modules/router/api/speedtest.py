from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from quart import Blueprint, current_app
from quart_rate_limiter import rate_limit

from modules.endpoints.internal.speedtest.download import download_speedtest_func

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue


api_v1_speedtest_bp = Blueprint("api_v1_speedtest", __name__, url_prefix="/api/v1")


@api_v1_speedtest_bp.route("/speedtest/<file_id>", methods=["GET"])
@rate_limit(4, timedelta(minutes=1))
async def speedtest_download(file_id: str) -> ResponseReturnValue:
    config_quart: dict = current_app.config_quart  # noqa
    return await download_speedtest_func(config=config_quart, file_id=file_id)
