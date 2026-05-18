from __future__ import annotations

from ipaddress import AddressValueError, ip_address
from typing import Any, Callable, List, Optional

from quart import request as quart_request

_LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")


class ProxyHeadersMiddleware:
    def __init__(self, app: Any, config: dict) -> None:
        self.app: Any = app
        self._config: dict = config

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        """
        Traite chaque requête ASGI et réécrit l'IP cliente si le proxy est de confiance.

        Parameters:
            scope (dict): scope ASGI de la requête entrante.
            receive (Callable): callable de réception des messages ASGI.
            send (Callable): callable d'envoi des messages ASGI.
        """
        if scope["type"] in ("http", "websocket"):
            client = scope.get("client")
            if client and client[0] in self._config["trusted_proxy_hosts"]:
                headers = dict(scope.get("headers", []))
                real_ip = self._resolve_client_ip(headers)
                if real_ip:
                    scope = dict(scope)
                    scope["client"] = (real_ip, client[1])
        await self.app(scope, receive, send)

    def _resolve_client_ip(self, headers: dict) -> str:
        """
        Détermine l'IP cliente à partir des en-têtes posés par le proxy de confiance.

        Parameters:
            headers (dict): en-têtes ASGI bruts de la requête.

        Returns:
            str: IP cliente retenue, ou chaîne vide si indisponible.
        """
        edge_ip = headers.get(b"x-real-ip", b"").decode().strip()
        if self._config["cloudflare"]["enabled"]:
            cf_ip = self._cloudflare_client_ip(headers, edge_ip)
            if cf_ip:
                return cf_ip

        return edge_ip

    def _cloudflare_client_ip(self, headers: dict, edge_ip: str) -> Optional[str]:
        """
        Retourne l'IP de l'en-tête CF-Connecting-IP si la requête provient de Cloudflare.

        Parameters:
            headers (dict): en-têtes ASGI bruts de la requête.
            edge_ip (str): IP ayant contacté le reverse proxy (en-tête X-Real-IP).

        Returns:
            Optional[str]: IP réelle du visiteur, ou None si la requête ne vient pas de Cloudflare.
        """
        cf_ip = headers.get(b"cf-connecting-ip", b"").decode().strip()
        if not cf_ip or not edge_ip:
            return None

        try:
            edge = ip_address(edge_ip)
        except (AddressValueError, ValueError):
            return None

        for net in self._config["cloudflare_nets"]:
            if edge.version == net.version and edge in net:
                return cf_ip

        return None


class TrustedHostMiddleware:
    def __init__(self, app: Any, allowed_hosts: Optional[List[str]] = None) -> None:
        hosts = [h.strip().lower() for h in (allowed_hosts or []) if h.strip()]
        self.app: Any = app
        self.allow_any: bool = not hosts or "*" in hosts
        self.allowed_hosts: List[str] = hosts + [h for h in _LOOPBACK_HOSTS if h not in hosts]

    def _is_allowed(self, host: str) -> bool:
        """
        Indique si un nom d'hôte correspond à la liste blanche.

        Gère la correspondance exacte et les motifs génériques « *.domaine ».

        Parameters:
            host (str): nom d'hôte issu de l'en-tête Host, sans port ni casse.

        Returns:
            bool: True si l'hôte est autorisé.
        """
        for pattern in self.allowed_hosts:
            if host == pattern:
                return True
            if pattern.startswith("*.") and host.endswith(pattern[1:]):
                return True
        return False

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        """
        Rejette les requêtes HTTP dont l'en-tête Host n'est pas dans la liste blanche.

        Renvoie 400 si l'hôte n'est pas reconnu. La validation est désactivée
        quand aucun hôte n'est configuré (allowed_hosts vide ou contenant « * »).

        Parameters:
            scope (dict): scope ASGI de la requête entrante.
            receive (Callable): callable de réception des messages ASGI.
            send (Callable): callable d'envoi des messages ASGI.
        """
        if self.allow_any or scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        host = headers.get(b"host", b"").decode().split(":")[0].strip().lower()
        if self._is_allowed(host):
            await self.app(scope, receive, send)
        else:
            await _reject_host(send)


async def _reject_host(send: Callable) -> None:
    """
    Envoie une réponse HTTP 400 pour un en-tête Host non autorisé.

    Parameters:
        send (Callable): callable d'envoi des messages ASGI.
    """
    await send({
        "type": "http.response.start",
        "status": 400,
        "headers": [(b"content-type", b"text/plain; charset=utf-8")],
    })
    await send({"type": "http.response.body", "body": b"Invalid host header"})


def get_client_ip(return_unknown: bool = False) -> Optional[str]:
    """
    Récupère l'IP cliente depuis le scope ASGI réécrit par ProxyHeadersMiddleware.

    Ne lit jamais les en-têtes de proxy directement afin d'éviter le spoofing d'IP.
    L'IP est normalisée via ipaddress pour garantir un format canonique.

    Parameters:
        return_unknown (bool): si True, retourne "Unknown" quand l'IP est indisponible.

    Returns:
        Optional[str]: adresse IP canonique, "Unknown" si introuvable et return_unknown=True, sinon None.
    """
    ip = quart_request.remote_addr
    try:
        ip = str(ip_address(ip)) if ip else None
    except (AddressValueError, ValueError):
        ip = None
    if ip is None:
        ip = "Unknown" if return_unknown else None
    return ip
