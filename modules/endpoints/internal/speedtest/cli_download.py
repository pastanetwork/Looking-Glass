from __future__ import annotations

from typing import TYPE_CHECKING

from quart import Response, jsonify

from modules.utility.middleware import get_client_ip

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue

    from modules.services.speedtest_service import SpeedtestService


async def cli_download_speedtest_func(config: dict, file_id: str, token: str) -> ResponseReturnValue:
    speedtest_service: SpeedtestService = config["speedtest_service"]
    client_ip = get_client_ip() or ""

    if not speedtest_service.enabled:
        return jsonify({"status": "Error", "status_code": 404, "detail": "err_generic"}), 404

    if not await speedtest_service.cli_token_valid(token):
        return jsonify({"status": "Error", "status_code": 403, "detail": "err_turnstile"}), 403

    start = await speedtest_service.begin(file_id, client_ip, token)
    if not start.ok:
        body = jsonify({"status": "Error", "status_code": start.http, "detail": start.error})
        if start.http == 503:
            body.headers["Retry-After"] = "60"

        return body, start.http

    response = Response("", status=200)
    response.headers["X-Accel-Redirect"] = start.accel_uri
    response.headers["Content-Type"] = "application/octet-stream"
    response.headers["Content-Disposition"] = f'attachment; filename="speedtest-{file_id}.bin"'
    response.headers["Cache-Control"] = "no-store"
    response.headers["Accept-Ranges"] = "none"

    return response
