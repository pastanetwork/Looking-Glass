from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import redis.asyncio as redis

from modules.constants import redis_keys
from modules.constants.limits import CONCURRENCY_SLOT_TTL

if TYPE_CHECKING:
    import logging


# Réservation atomique des deux compteurs : INCR + EXPIRE + contrôle de plafond
# en un seul aller-retour, pour qu'aucun chemin ne laisse un slot sans TTL ni un
# compteur incrémenté à moitié. Retourne 0 (ok), 1 (plafond global), 2 (plafond IP).
_ACQUIRE_LUA = """
local gcount = redis.call('INCR', KEYS[1])
redis.call('EXPIRE', KEYS[1], ARGV[3])
if gcount > tonumber(ARGV[1]) then
  redis.call('DECR', KEYS[1])
  return 1
end
local icount = redis.call('INCR', KEYS[2])
redis.call('EXPIRE', KEYS[2], ARGV[3])
if icount > tonumber(ARGV[2]) then
  redis.call('DECR', KEYS[2])
  redis.call('DECR', KEYS[1])
  return 2
end
return 0
"""


@dataclass
class AcquireResult:
    ok: bool
    http: int = 200
    error: str = ""


class ConcurrencyService:
    def __init__(self, redis_pool: redis.ConnectionPool, config: dict, logger: logging.Logger) -> None:
        self._pool = redis_pool
        self._global_cap = int(config["global_command_cap"])
        self._per_ip_cap = int(config["per_ip_command_cap"])
        self._logger = logger

    async def acquire(self, ip_hash: str) -> AcquireResult:
        """
        Réserve un slot d'exécution global et par IP, de façon atomique.

        Parameters:
            ip_hash (str): empreinte hachée de l'IP source.

        Returns:
            AcquireResult: résultat de la réservation (ok, code HTTP, message d'erreur).
        """
        client = redis.Redis(connection_pool=self._pool)
        try:
            outcome = await client.eval(
                _ACQUIRE_LUA,
                2,
                redis_keys.concurrency_global(),
                redis_keys.concurrency_ip(ip_hash),
                self._global_cap,
                self._per_ip_cap,
                CONCURRENCY_SLOT_TTL
            )
        except Exception as e:
            self._logger.error("Concurrence indisponible (Redis) : %s", e)
            return AcquireResult(ok=False, http=503, error="err_busy")

        if outcome == 1:
            return AcquireResult(ok=False, http=503, error="err_busy")
        if outcome == 2:
            return AcquireResult(ok=False, http=429, error="err_ratelimit")

        return AcquireResult(ok=True)

    async def release(self, ip_hash: str) -> None:
        """
        Libère un slot d'exécution.

        Parameters:
            ip_hash (str): empreinte hachée de l'IP source.
        """
        client = redis.Redis(connection_pool=self._pool)
        try:
            for key in (redis_keys.concurrency_global(), redis_keys.concurrency_ip(ip_hash)):
                value = await client.decr(key)
                if value < 0:
                    await client.set(key, 0)
        except Exception as e:
            self._logger.warning("Libération de slot échouée : %s", e)
