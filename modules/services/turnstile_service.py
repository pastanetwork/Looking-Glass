from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import aiohttp

from modules.constants.limits import TURNSTILE_TIMEOUT_SECONDS, TURNSTILE_VERIFY_URL

if TYPE_CHECKING:
    import logging


class TurnstileService:
    def __init__(self, config: dict, logger: logging.Logger) -> None:
        self._secret = config["turnstile"]["secret_key"]
        self._dev_bypass = bool(config["dev"] and config["turnstile"]["dev_bypass"])
        self._logger = logger
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def bypassed(self) -> bool:
        """Indique si la vérification est court-circuitée (dev uniquement)."""
        return self._dev_bypass

    def _get_session(self) -> aiohttp.ClientSession:
        """
        Retourne la session HTTP, en la recréant si elle a été fermée.

        Une session fermée ne se rouvre pas seule : sans cette reconstruction,
        une fermeture accidentelle bloquerait définitivement toute vérification.

        Returns:
            aiohttp.ClientSession: session ouverte, prête à émettre une requête.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def verify(self, token: str, remote_ip: Optional[str]) -> bool:
        """
        Vérifie un token Turnstile auprès de l'API Cloudflare.

        Parameters:
            token (str): token Turnstile fourni par le client.
            remote_ip (Optional[str]): adresse IP du client, transmise à Cloudflare si disponible.

        Returns:
            bool: True si le token est valide, False dans tous les autres cas.
        """
        if self._dev_bypass:
            return True
        if not token or not self._secret:
            return False

        data = {"secret": self._secret, "response": token}
        if remote_ip:
            data["remoteip"] = remote_ip

        try:
            async with self._get_session().post(
                TURNSTILE_VERIFY_URL,
                data=data,
                timeout=aiohttp.ClientTimeout(total=TURNSTILE_TIMEOUT_SECONDS),
            ) as resp:
                if resp.status != 200:
                    self._logger.warning("Turnstile a répondu avec le statut %s", resp.status)
                    return False
                result = await resp.json(content_type=None)
                return bool(result.get("success"))
        except Exception as e:
            self._logger.warning("Vérification Turnstile échouée : %s", e)
            return False

    async def aclose(self) -> None:
        """Ferme la session HTTP si elle est encore ouverte."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None
