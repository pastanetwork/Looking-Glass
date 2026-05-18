from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from quart import Blueprint, current_app, request
from quart_rate_limiter import rate_limit

from modules.endpoints.internal.speedtest.cli_download import cli_download_speedtest_func
from modules.endpoints.internal.speedtest.cli_script import cli_script_func
from modules.endpoints.internal.speedtest.cli_token import cli_token_func

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue


api_v1_speedtest_bp = Blueprint("api_v1_speedtest", __name__, url_prefix="/api/v1")


@api_v1_speedtest_bp.route("/speedtest/cli-token", methods=["POST"])
@rate_limit(4, timedelta(minutes=1))
async def speedtest_cli_token() -> ResponseReturnValue:
    config_quart: dict = current_app.config_quart  # noqa
    payload = await request.get_json(silent=True) or {}
    return await cli_token_func(
        config=config_quart,
        file_id=str(payload.get("file_id", "")),
        turnstile_token=request.headers.get("X-Turnstile-Token", ""),
    )


@api_v1_speedtest_bp.route("/speedtest/cli/<file_id>", methods=["GET"])
@rate_limit(16, timedelta(minutes=1))
async def speedtest_cli_download(file_id: str) -> ResponseReturnValue:
    config_quart: dict = current_app.config_quart  # noqa
    return await cli_download_speedtest_func(
        config=config_quart,
        file_id=file_id,
        token=request.args.get("token", ""),
    )


@api_v1_speedtest_bp.route("/speedtest/cli/script/<file_id>", methods=["GET"])
@rate_limit(10, timedelta(minutes=1))
async def speedtest_cli_script(file_id: str) -> ResponseReturnValue:
    config_quart: dict = current_app.config_quart  # noqa
    return await cli_script_func(
        config=config_quart,
        file_id=file_id,
        token=request.args.get("token", ""),
        os_name=request.args.get("os", ""),
        lang=request.args.get("lang", ""),
    )
