from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import redis.asyncio as redis
from quart import jsonify

if TYPE_CHECKING:
    import logging

    from quart.typing import ResponseReturnValue


async def health_func(config: dict) -> ResponseReturnValue:
    logger: logging.Logger = config["logger"]
    checks = {"database": False, "redis": False}

    db = config.get("db")
    if db is not None:
        try:
            await db.execute("SELECT 1")
            checks["database"] = True
        except Exception as e:
            logger.debug("Sonde de santé base échouée : %s", e)

    redis_pool: Optional[redis.ConnectionPool] = config.get("redis_pool")
    if redis_pool is not None:
        try:
            client = redis.Redis(connection_pool=redis_pool)
            await client.ping()
            checks["redis"] = True
        except Exception as e:
            logger.debug("Sonde de santé Redis échouée : %s", e)

    healthy = all(checks.values())
    status_code = 200 if healthy else 503

    return jsonify({
        "status": "Ok" if healthy else "Unavailable",
        "status_code": status_code,
        "data": {"checks": checks},
    }), status_code
