from __future__ import annotations

import contextlib
from typing import Any

import redis.asyncio as redis
from quart_rate_limiter.redis_store import RedisStore


class ResilientRedisStore(RedisStore):

    async def get(self, key: str, default: Any) -> Any:
        """
        Lit une valeur dans Redis en mode fail-open.

        Retourne la valeur par défaut si Redis est indisponible plutôt que
        de laisser l'exception se propager.

        Parameters:
            key (str): clé Redis à lire.
            default (Any): valeur retournée en cas d'erreur ou de clé absente.

        Returns:
            Any: valeur lue ou valeur par défaut.
        """
        try:
            return await super().get(key, default)
        except Exception:
            return default

    async def set(self, key: str, tat: Any) -> None:
        """
        Écrit une valeur dans Redis en mode fail-open (les erreurs sont silencieuses).

        Parameters:
            key (str): clé Redis à écrire.
            tat (Any): valeur à stocker (timestamp d'autorisation pour le rate-limiter).
        """
        with contextlib.suppress(Exception):
            await super().set(key, tat)

    async def after_serving(self) -> None:
        """Ferme la connexion Redis proprement à la fin du service, en ignorant les erreurs."""
        if self._redis is not None:
            with contextlib.suppress(Exception):
                await self._redis.aclose()
            self._redis = None


def create_redis_pool(config: dict) -> redis.ConnectionPool:
    """
    Crée le pool de connexions Redis partagé pour l'application.

    Utilisé pour les compteurs de concurrence, les budgets speedtest et
    toutes les clés applicatives dans l'espace de noms "lg:".

    Parameters:
        config (dict): configuration de l'application contenant redis_host, redis_port et redis_password.

    Returns:
        redis.ConnectionPool: pool de connexions Redis prêt à l'emploi.
    """
    return redis.ConnectionPool(
        host=config["redis_host"],
        port=config["redis_port"],
        password=config["redis_password"] or None,
        encoding="utf-8",
        decode_responses=True,
        health_check_interval=1,
        socket_connect_timeout=5,
        socket_keepalive=True,
        retry_on_timeout=True,
        db=0,
    )


def build_redis_store(config: dict) -> ResilientRedisStore:
    """
    Construit le store Redis résilient utilisé par le rate-limiter Quart.

    Parameters:
        config (dict): configuration de l'application contenant redis_host, redis_port et redis_password.

    Returns:
        ResilientRedisStore: store Redis en mode fail-open pour le rate-limiter.
    """
    url = f"redis://{config['redis_host']}:{config['redis_port']}"
    return ResilientRedisStore(
        url,
        password=config["redis_password"] or None,
        db=0,
        encoding="utf-8",
        health_check_interval=1,
        socket_connect_timeout=5,
        socket_keepalive=True,
        retry_on_timeout=True,
    )
