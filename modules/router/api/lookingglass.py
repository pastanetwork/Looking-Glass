from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from quart import Blueprint, current_app
from quart_rate_limiter import rate_limit

from modules.endpoints.internal.commands.list_nodes import list_nodes_func
from modules.endpoints.internal.commands.run_command import run_command_func

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue


api_v1_lg_bp = Blueprint("api_v1_lg", __name__, url_prefix="/api/v1")


@api_v1_lg_bp.route("/run", methods=["POST"])
@rate_limit(20, timedelta(minutes=1))
async def run_post() -> ResponseReturnValue:
    config_quart: dict = current_app.config_quart  # noqa
    return await run_command_func(config=config_quart)


@api_v1_lg_bp.route("/nodes", methods=["GET"])
@rate_limit(60, timedelta(minutes=1))
async def nodes_get() -> ResponseReturnValue:
    config_quart: dict = current_app.config_quart  # noqa
    return await list_nodes_func(config=config_quart)
