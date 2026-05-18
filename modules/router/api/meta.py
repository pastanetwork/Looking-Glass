from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from quart import Blueprint, current_app
from quart_rate_limiter import rate_limit

from modules.endpoints.internal.meta.client_ip import client_ip_func
from modules.endpoints.internal.meta.health import health_func

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue


api_v1_meta_bp = Blueprint("api_v1_meta", __name__, url_prefix="/api/v1")


@api_v1_meta_bp.route("/health", methods=["GET"])
@rate_limit(30, timedelta(minutes=1))
async def health_get() -> ResponseReturnValue:
    config_quart: dict = current_app.config_quart  # noqa
    return await health_func(config=config_quart)


@api_v1_meta_bp.route("/ip", methods=["GET"])
@rate_limit(30, timedelta(minutes=1))
async def ip_get() -> ResponseReturnValue:
    return await client_ip_func()
