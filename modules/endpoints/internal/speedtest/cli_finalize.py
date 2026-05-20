from __future__ import annotations

import hmac
from typing import TYPE_CHECKING

from quart import Response, request

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue

    from modules.services.speedtest_service import SpeedtestService


async def cli_finalize_func(config: dict) -> ResponseReturnValue:
    speedtest_service: SpeedtestService = config["speedtest_service"]
    if not speedtest_service.enabled:
        return Response("", status=204)

    client_ip = request.remote_addr or ""
    trusted = config.get("trusted_proxy_hosts") or []
    if client_ip not in trusted:
        return Response("forbidden", status=403)

    provided = request.headers.get("X-Speedtest-Auth", "")
    expected = speedtest_service.finalize_secret
    if not expected or not hmac.compare_digest(provided, expected):
        return Response("forbidden", status=403)

    token = request.headers.get("X-Speedtest-Token", "")
    rid = request.headers.get("X-Speedtest-Rid", "")
    if not token or not rid:
        return Response("", status=204)

    file_id = request.headers.get("X-Speedtest-File", "")
    if file_id.endswith(".bin"):
        file_id = file_id[:-4]

    bytes_sent = int(request.headers.get("X-Speedtest-Sent", "0"))
    status = int(request.headers.get("X-Speedtest-Status", "0"))

    await speedtest_service.finalize(
        token=token,
        rid=rid,
        file_id=file_id,
        bytes_sent=bytes_sent,
        status=status,
    )

    return Response("", status=204)
