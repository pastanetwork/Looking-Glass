from __future__ import annotations

from typing import TYPE_CHECKING

from quart import Response, jsonify

from modules.utility.middleware import get_client_ip

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue

    from modules.services.speedtest_service import SpeedtestService


async def download_speedtest_func(config: dict, file_id: str) -> ResponseReturnValue:
    speedtest_service: SpeedtestService = config["speedtest_service"]
    client_ip = get_client_ip() or ""

    start = await speedtest_service.begin(file_id, client_ip)
    if not start.ok:
        body = jsonify({"status": "Error", "status_code": start.http, "detail": start.error})
        if start.http == 503:
            body.headers["Retry-After"] = "60"
        return body, start.http

    response = Response(
        speedtest_service.stream(file_id, start.size, client_ip),
        content_type="application/octet-stream",
    )

    safe_id = "".join(c for c in file_id if c.isalnum())

    response.headers["Content-Length"] = str(start.size)
    response.headers["Content-Disposition"] = f'attachment; filename="speedtest-{safe_id}.bin"'
    response.headers["Cache-Control"] = "no-store"
    response.timeout = None

    return response
