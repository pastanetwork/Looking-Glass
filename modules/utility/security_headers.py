from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quart import Response


_CSP_DIRECTIVES: dict[str, list[str]] = {
    "default-src": ["'self'"],
    "script-src": [
        "'self'", "'unsafe-inline'", "'unsafe-eval'",
        "https://cdn.tailwindcss.com",
        "https://cdn.jsdelivr.net",
        "https://cdnjs.cloudflare.com",
        "https://challenges.cloudflare.com",
    ],
    "style-src": [
        "'self'", "'unsafe-inline'",
        "https://cdn.tailwindcss.com",
        "https://cdnjs.cloudflare.com",
        "https://cdn.jsdelivr.net",
    ],
    "img-src": ["'self'", "data:", "https://flagcdn.com"],
    "font-src": ["'self'", "https://cdnjs.cloudflare.com"],
    "connect-src": ["'self'", "https://challenges.cloudflare.com", "https://cdn.jsdelivr.net"],
    "frame-src": ["https://challenges.cloudflare.com"],
    "frame-ancestors": ["'none'"],
    "base-uri": ["'self'"],
}

_CONTENT_SECURITY_POLICY = "; ".join(
    f"{directive} {' '.join(sources)}" for directive, sources in _CSP_DIRECTIVES.items()
)

_SECURITY_HEADERS: dict[str, str] = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": _CONTENT_SECURITY_POLICY,
}


def apply_security_headers(response: Response) -> Response:
    """
    Pose les en-têtes de sécurité HTTP sur chaque réponse sortante.

    Parameters:
        response (Response): objet réponse Quart à enrichir.

    Returns:
        Response: même objet réponse avec les en-têtes de sécurité ajoutés.
    """
    for name, value in _SECURITY_HEADERS.items():
        response.headers[name] = value
    return response
