from __future__ import annotations

from typing import TYPE_CHECKING

from quart import Response, jsonify, request

from modules.utility.i18n import make_translator
from modules.utility.speedtest_script import SUPPORTED_OS, build_speedtest_script

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue

    from modules.services.speedtest_service import SpeedtestService


def _text(body: str) -> Response:
    """
    Emballe un corps de script dans une réponse texte non mise en cache.

    Parameters:
        body (str): contenu du script à renvoyer.

    Returns:
        Response: réponse HTTP en text/plain, sans mise en cache.
    """
    response = Response(body, content_type="text/plain; charset=utf-8")
    response.headers["Cache-Control"] = "no-store"
    return response


async def cli_script_func(config: dict, file_id: str, token: str, os_name: str, lang: str) -> ResponseReturnValue:
    speedtest_service: SpeedtestService = config["speedtest_service"]

    if not speedtest_service.enabled:
        return jsonify({"status": "Error", "status_code": 404, "detail": "err_generic"}), 404

    size = speedtest_service.resolve_size(file_id)
    if size is None or os_name not in SUPPORTED_OS:
        return jsonify({"status": "Error", "status_code": 404, "detail": "err_generic"}), 404

    translations = config["translations"]
    default = config["default_language"]
    t = make_translator(translations, lang if lang in translations else default, default)

    if not await speedtest_service.cli_token_valid(token):
        message = t("speedtest_cli_expired")
        body = f'echo "{message}"' if os_name == "linux" else f'Write-Host "{message}"'
        return _text(body)

    base = (config.get("public_url") or request.host_url).rstrip("/")
    script = build_speedtest_script(
        os_name,
        download_url=f"{base}/api/v1/speedtest/cli/{file_id}?token={token}",
        total=size,
        live=t("speedtest_cli_live"),
        conn=t("speedtest_cli_conn"),
        total_label=t("speedtest_cli_total"),
        volume_label=t("speedtest_volume"),
        duration_label=t("speedtest_elapsed"),
        unit=t("speedtest_cli_unit"),
    )

    return _text(script or "")
