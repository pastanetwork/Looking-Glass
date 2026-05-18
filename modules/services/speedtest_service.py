from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, AsyncIterator, List, Optional

import redis.asyncio as redis

from modules.constants import redis_keys
from modules.constants.limits import (
    SPEEDTEST_BUDGET_TTL,
    SPEEDTEST_CHUNK_SIZE,
    SPEEDTEST_CONCURRENCY_CAP,
    SPEEDTEST_FLUSH_EVERY,
    SPEEDTEST_MAX_FILE_BYTES,
    SPEEDTEST_SLOT_TTL,
)
from modules.utility.hashing import hash_ip

if TYPE_CHECKING:
    import logging

    from modules.repositories.query_log_repo import QueryLogRepository


@dataclass
class SpeedtestStart:
    ok: bool
    http: int = 200
    error: str = ""
    size: int = 0


class SpeedtestService:
    def __init__(
        self,
        redis_pool: redis.ConnectionPool,
        config: dict,
        query_log: QueryLogRepository,
        logger: logging.Logger,
    ) -> None:
        self._pool = redis_pool
        self._query_log = query_log
        self._logger = logger
        self._salt = config["ip_hash_salt"]
        st: dict = config["speedtest"]
        self._enabled = bool(st.get("enabled", False))
        self._max_file_size = int(st.get("max_file_size_bytes") or SPEEDTEST_MAX_FILE_BYTES)
        self._files = self._load_files(st.get("files", []))
        self._daily_budget = int(st.get("daily_byte_budget", 0))
        self._per_ip_budget = int(st.get("per_ip_byte_budget", 0))
        self._max_kbps = int(st.get("max_kbps", 0))
        self._concurrency_cap = int(st.get("concurrency", SPEEDTEST_CONCURRENCY_CAP))

    @staticmethod
    def _load_files(raw: List[dict]) -> dict:
        """
        Valide et indexe les fichiers de test déclarés en configuration.

        Parameters:
            raw (List[dict]): liste brute des fichiers issue de la configuration.

        Returns:
            dict: fichiers valides indexés par identifiant.

        Raises:
            ValueError: si une entrée n'a pas d'identifiant unique ou de taille positive valide.
        """
        files: dict = {}
        for entry in raw:
            fid = str(entry.get("id", "")).strip()
            if not fid:
                raise ValueError("Fichier speedtest sans identifiant dans la configuration.")
            if fid in files:
                raise ValueError(f"Fichier speedtest '{fid}' : identifiant en double.")

            try:
                size = int(entry["size_bytes"])
            except (KeyError, TypeError, ValueError):
                raise ValueError(f"Fichier speedtest '{fid}' : size_bytes manquant ou invalide.") from None
            if size <= 0:
                raise ValueError(f"Fichier speedtest '{fid}' : size_bytes doit être strictement positif.")

            files[fid] = {"id": fid, "label": str(entry.get("label", fid)), "size_bytes": size}

        return files

    @property
    def enabled(self) -> bool:
        """Indique si la fonctionnalité speedtest est activée."""
        return self._enabled

    def files(self) -> List[dict]:
        """
        Retourne la liste des fichiers de test exposés avec leurs tailles plafonnées.

        Returns:
            List[dict]: liste de dictionnaires contenant id, label et size_bytes.
        """
        return [
            {
                "id": fid,
                "label": f.get("label", fid),
                "size_bytes": min(f["size_bytes"], self._max_file_size),
            }
            for fid, f in self._files.items()
        ]

    def resolve_size(self, file_id: str) -> Optional[int]:
        """
        Retourne la taille plafonnée du fichier identifié, ou None si inconnu.

        Parameters:
            file_id (str): identifiant du fichier de test (ex. '10mb', '100mb').

        Returns:
            Optional[int]: taille en octets plafonnée, ou None si l'id est introuvable.
        """
        f = self._files.get(file_id)
        return min(f["size_bytes"], self._max_file_size) if f else None

    def _hash(self, ip: str) -> str:
        """
        Hache une adresse IP avec le sel de configuration.

        Parameters:
            ip (str): adresse IP du client.

        Returns:
            str: empreinte hexadécimale SHA-256 de l'IP.
        """
        return hash_ip(ip, self._salt)

    @staticmethod
    def _today() -> str:
        """
        Retourne la date UTC du jour au format YYYYMMDD.

        Returns:
            str: date du jour en UTC, formatée YYYYMMDD.
        """
        return datetime.now(UTC).strftime("%Y%m%d")

    async def begin(self, file_id: str, client_ip: str) -> SpeedtestStart:
        """
        Vérifie la disponibilité, la concurrence et le budget, puis réserve un slot.

        Parameters:
            file_id (str): identifiant du fichier de test demandé.
            client_ip (str): adresse IP du client.

        Returns:
            SpeedtestStart: résultat de la réservation avec la taille validée.
        """
        if not self._enabled:
            return SpeedtestStart(ok=False, http=404, error="err_generic")

        size = self.resolve_size(file_id)
        if size is None:
            return SpeedtestStart(ok=False, http=404, error="err_generic")

        client = redis.Redis(connection_pool=self._pool)
        try:
            count = await client.incr(redis_keys.speedtest_concurrency())
            await client.expire(redis_keys.speedtest_concurrency(), SPEEDTEST_SLOT_TTL)
            if count > self._concurrency_cap:
                await client.decr(redis_keys.speedtest_concurrency())
                return SpeedtestStart(ok=False, http=503, error="err_busy")
        except Exception as e:
            self._logger.warning("Speedtest indisponible (Redis) : %s", e)
            return SpeedtestStart(ok=False, http=503, error="err_busy")

        if not await self._budget_ok(client, self._hash(client_ip), size):
            await self._release(client)
            return SpeedtestStart(ok=False, http=503, error="err_busy")

        return SpeedtestStart(ok=True, size=size)

    async def stream(self, file_id: str, size: int, client_ip: str) -> AsyncIterator[bytes]:
        """
        Génère les octets du fichier de test en bridant le débit et en comptabilisant le trafic.

        Parameters:
            file_id (str): identifiant du fichier de test, conservé pour le journal.
            size (int): nombre total d'octets à envoyer.
            client_ip (str): adresse IP du client pour le suivi du budget.
        """
        client = redis.Redis(connection_pool=self._pool)
        ip_hash = self._hash(client_ip)

        day = self._today()
        started = time.monotonic()

        full_chunk = b"\x00" * SPEEDTEST_CHUNK_SIZE
        bytes_per_sec = self._max_kbps * 1024 if self._max_kbps > 0 else 0

        sent = 0
        pending = 0
        chunks = 0

        try:
            while sent < size:
                remaining = size - sent
                piece = full_chunk if remaining >= SPEEDTEST_CHUNK_SIZE else b"\x00" * remaining
                yield piece

                sent += len(piece)
                pending += len(piece)
                chunks += 1

                if chunks % SPEEDTEST_FLUSH_EVERY == 0:
                    await self._flush(client, day, ip_hash, pending)
                    pending = 0
                    if self._daily_budget and await self._over_daily(client, day):
                        break
                if bytes_per_sec:
                    ahead = (sent / bytes_per_sec) - (time.monotonic() - started)
                    if ahead > 0:
                        await asyncio.sleep(ahead)
        finally:
            if pending:
                with contextlib.suppress(Exception):
                    await self._flush(client, day, ip_hash, pending)
            await self._release(client)
            await self._query_log.create(
                node_id="local",
                command_type="speedtest",
                target=file_id,
                family=None,
                source_ip_hash=ip_hash,
                status="ok" if sent >= size else "killed",
                exit_code=None,
                duration_ms=int((time.monotonic() - started) * 1000),
                bytes_served=sent,
            )

    async def _flush(self, client: redis.Redis, day: str, ip_hash: str, count: int) -> None:
        """
        Incrémente les compteurs de budget Redis pour la journée et l'IP (best-effort).

        Parameters:
            client (redis.Redis): client Redis actif.
            day (str): clé de date au format YYYYMMDD.
            ip_hash (str): empreinte hachée de l'IP source.
            count (int): nombre d'octets à comptabiliser.
        """
        with contextlib.suppress(Exception):
            day_key = redis_keys.speedtest_bytes_day(day)
            ip_key = redis_keys.speedtest_bytes_ip(ip_hash, day)
            await client.incrby(day_key, count)
            await client.expire(day_key, SPEEDTEST_BUDGET_TTL)
            await client.incrby(ip_key, count)
            await client.expire(ip_key, SPEEDTEST_BUDGET_TTL)

    async def _budget_ok(self, client: redis.Redis, ip_hash: str, size: int) -> bool:
        """
        Vérifie que les budgets quotidien et par IP permettent le téléchargement demandé.

        Parameters:
            client (redis.Redis): client Redis actif.
            ip_hash (str): empreinte hachée de l'IP source.
            size (int): taille en octets du fichier demandé.

        Returns:
            bool: True si les budgets sont suffisants ou non configurés, False sinon.
        """
        day = self._today()

        try:
            if self._daily_budget:
                used = int(await client.get(redis_keys.speedtest_bytes_day(day)) or 0)
                if used + size > self._daily_budget:
                    return False

            if self._per_ip_budget:
                used_ip = int(await client.get(redis_keys.speedtest_bytes_ip(ip_hash, day)) or 0)
                if used_ip + size > self._per_ip_budget:
                    return False
        except Exception as e:
            self._logger.warning("Vérification du budget speedtest échouée : %s", e)
            return not (self._daily_budget or self._per_ip_budget)

        return True

    async def _over_daily(self, client: redis.Redis, day: str) -> bool:
        """
        Indique si le budget quotidien global est dépassé.

        Parameters:
            client (redis.Redis): client Redis actif.
            day (str): clé de date au format YYYYMMDD.

        Returns:
            bool: True si le budget est dépassé, False sinon ou en cas d'erreur Redis.
        """
        try:
            used = int(await client.get(redis_keys.speedtest_bytes_day(day)) or 0)
            return used > self._daily_budget
        except Exception:
            return False

    async def _release(self, client: redis.Redis) -> None:
        """
        Décrémente le compteur de concurrence speedtest dans Redis (best-effort).

        Parameters:
            client (redis.Redis): client Redis actif.
        """
        with contextlib.suppress(Exception):
            value = await client.decr(redis_keys.speedtest_concurrency())
            if value < 0:
                await client.set(redis_keys.speedtest_concurrency(), 0)
