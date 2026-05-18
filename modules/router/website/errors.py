from __future__ import annotations

from typing import TYPE_CHECKING

from quart import Quart, jsonify, render_template, request

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue


async def _error_response(code: int, message_key: str) -> ResponseReturnValue:
    """
    Retourne une réponse d'erreur adaptée au contexte.

    Parameters:
        code (int): code HTTP de l'erreur.
        message_key (str): clé de traduction du message d'erreur.
    """
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({"status": "Error", "status_code": code, "detail": message_key}), code
    return await render_template("error.html", error_code=code, error_message_key=message_key), code


def register_error_handlers(app: Quart) -> None:

    @app.errorhandler(404)
    async def _not_found(error: Exception) -> ResponseReturnValue:
        """Gestionnaire de l'erreur 404 (ressource introuvable)."""
        return await _error_response(404, "error_404")

    @app.errorhandler(429)
    async def _rate_limited(error: Exception) -> ResponseReturnValue:
        """Gestionnaire de l'erreur 429 (limite de requêtes atteinte)."""
        return await _error_response(429, "error_429")

    @app.errorhandler(500)
    async def _server_error(error: Exception) -> ResponseReturnValue:
        """Gestionnaire de l'erreur 500 (erreur interne du serveur)."""
        return await _error_response(500, "error_500")
