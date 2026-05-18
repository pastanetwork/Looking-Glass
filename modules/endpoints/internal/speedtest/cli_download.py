from __future__ import annotations

from typing import TYPE_CHECKING

from quart import Response, jsonify

from modules.utility.middleware import get_client_ip

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue

    from modules.services.speedtest_service import SpeedtestService


def _stream_response(speedtest_service: SpeedtestService, file_id: str, size: int, client_ip: str) -> Response:
    """
    Construit la réponse de streaming d'un fichier de test de débit.

    Parameters:
        speedtest_service (SpeedtestService): service produisant le flux d'octets.
        file_id (str): identifiant du fichier de test demandé.
        size (int): taille en octets à envoyer, déjà validée et plafonnée.
        client_ip (str): adresse IP du client pour le suivi du budget.

    Returns:
        Response: réponse HTTP en flux, sans mise en cache.
    """
    response = Response(
        speedtest_service.stream(file_id, size, client_ip),
        content_type="application/octet-stream",
    )

    safe_id = "".join(c for c in file_id if c.isalnum())

    response.headers["Content-Length"] = str(size)
    response.headers["Content-Disposition"] = f'attachment; filename="speedtest-{safe_id}.bin"'
    response.headers["Cache-Control"] = "no-store"
    response.timeout = None

    return response


async def cli_download_speedtest_func(config: dict, file_id: str, token: str) -> ResponseReturnValue:
    speedtest_service: SpeedtestService = config["speedtest_service"]
    client_ip = get_client_ip() or ""

    if not speedtest_service.enabled:
        return jsonify({"status": "Error", "status_code": 404, "detail": "err_generic"}), 404

    if not await speedtest_service.cli_token_valid(token):
        return jsonify({"status": "Error", "status_code": 403, "detail": "err_turnstile"}), 403

    start = await speedtest_service.begin(file_id, client_ip)
    if not start.ok:
        body = jsonify({"status": "Error", "status_code": start.http, "detail": start.error})
        if start.http == 503:
            body.headers["Retry-After"] = "60"

        return body, start.http

    return _stream_response(speedtest_service, file_id, start.size, client_ip)
