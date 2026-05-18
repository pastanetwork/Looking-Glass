from __future__ import annotations

from typing import TYPE_CHECKING

from quart import jsonify

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue

    from modules.services.stats_service import StatsService


async def stats_overview_func(config: dict) -> ResponseReturnValue:
    stats_service: StatsService = config["stats_service"]
    data = await stats_service.overview()

    return jsonify({"status": "Ok", "status_code": 200, "data": data}), 200
