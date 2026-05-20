from __future__ import annotations

import contextlib
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, List, Optional

import redis.asyncio as redis

from modules.constants import redis_keys
from modules.constants.limits import (
    SPEEDTEST_BUDGET_TTL,
    SPEEDTEST_CLI_TOKEN_TTL,
    SPEEDTEST_CONCURRENCY_CAP,
    SPEEDTEST_MAX_FILE_BYTES,
    SPEEDTEST_RESERVATION_GC_AGE,
    SPEEDTEST_RESERVATION_TTL,
    SPEEDTEST_SLOT_TTL,
    SPEEDTEST_TOKEN_MAX_USES,
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
    accel_uri: str = ""


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
        self._concurrency_cap = int(st.get("concurrency", SPEEDTEST_CONCURRENCY_CAP))
        self._finalize_secret = str(st.get("finalize_secret", ""))
        self._xaccel_prefix = str(st.get("xaccel_prefix", "/__internal__/speedtest")).rstrip("/")

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

    @property
    def cli_token_ttl(self) -> int:
        """Durée de validité, en secondes, d'un token de test de débit en ligne de commande."""
        return SPEEDTEST_CLI_TOKEN_TTL

    @property
    def finalize_secret(self) -> str:
        """Secret partagé attendu dans l'en-tête X-Speedtest-Auth émis par nginx."""
        return self._finalize_secret

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

    async def mint_cli_token(self) -> Optional[str]:
        """
        Génère un token éphémère autorisant un test de débit en ligne de commande.

        Returns:
            Optional[str]: token opaque, ou None si le speedtest est désactivé ou si Redis est indisponible.
        """
        if not self._enabled:
            return None

        token = secrets.token_urlsafe(24)
        client = redis.Redis(connection_pool=self._pool)

        try:
            await client.set(redis_keys.speedtest_cli_token(token), "1", ex=SPEEDTEST_CLI_TOKEN_TTL)
        except Exception as e:
            self._logger.warning("Création du token speedtest CLI échouée : %s", e)
            return None

        return token

    async def cli_token_valid(self, token: str) -> bool:
        """
        Indique si un token de test de débit en ligne de commande est encore valide.

        Parameters:
            token (str): token opaque fourni par le client en ligne de commande.

        Returns:
            bool: True si le token existe et n'a pas expiré, False sinon.
        """
        if not self._enabled or not token or len(token) > 64:
            return False

        client = redis.Redis(connection_pool=self._pool)

        try:
            return bool(await client.exists(redis_keys.speedtest_cli_token(token)))
        except Exception as e:
            self._logger.warning("Vérification du token speedtest CLI échouée : %s", e)
            return False

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

    async def begin(self, file_id: str, client_ip: str, token: str) -> SpeedtestStart:
        """
        Réserve un slot, pré-réserve les budgets puis prépare une URI X-Accel-Redirect.

        Parameters:
            file_id (str): identifiant du fichier de test demandé.
            client_ip (str): adresse IP du client.
            token (str): token CLI déjà validé, ré-utilisé comme racine de la réservation.

        Returns:
            SpeedtestStart: résultat de la réservation avec l'URI interne X-Accel.
        """
        if not self._enabled:
            return SpeedtestStart(ok=False, http=404, error="err_generic")

        size = self.resolve_size(file_id)
        if size is None:
            return SpeedtestStart(ok=False, http=404, error="err_generic")

        client = redis.Redis(connection_pool=self._pool)
        ip_hash = self._hash(client_ip)
        day = self._today()
        day_key = redis_keys.speedtest_bytes_day(day)
        ip_key = redis_keys.speedtest_bytes_ip(ip_hash, day)

        uses_key = redis_keys.speedtest_cli_token_uses(token)
        try:
            uses = await client.incr(uses_key)
            await client.expire(uses_key, SPEEDTEST_CLI_TOKEN_TTL)
            if uses > SPEEDTEST_TOKEN_MAX_USES:
                return SpeedtestStart(ok=False, http=410, error="err_token_exhausted")
        except Exception as e:
            self._logger.warning("Compteur d'utilisations speedtest échoué : %s", e)
            return SpeedtestStart(ok=False, http=503, error="err_busy")

        try:
            count = await client.incr(redis_keys.speedtest_concurrency())
            await client.expire(redis_keys.speedtest_concurrency(), SPEEDTEST_SLOT_TTL)
            if count > self._concurrency_cap:
                await client.decr(redis_keys.speedtest_concurrency())
                return SpeedtestStart(ok=False, http=503, error="err_busy")
        except Exception as e:
            self._logger.warning("Speedtest indisponible (Redis) : %s", e)
            return SpeedtestStart(ok=False, http=503, error="err_busy")

        try:
            if self._daily_budget:
                new_day = await client.incrby(day_key, size)
                await client.expire(day_key, SPEEDTEST_BUDGET_TTL)
                if new_day > self._daily_budget:
                    await client.decrby(day_key, size)
                    await self._release_slot(client)
                    return SpeedtestStart(ok=False, http=503, error="err_busy")

            if self._per_ip_budget:
                new_ip = await client.incrby(ip_key, size)
                await client.expire(ip_key, SPEEDTEST_BUDGET_TTL)
                if new_ip > self._per_ip_budget:
                    await client.decrby(ip_key, size)
                    if self._daily_budget:
                        await client.decrby(day_key, size)
                    await self._release_slot(client)
                    return SpeedtestStart(ok=False, http=503, error="err_busy")
        except Exception as e:
            self._logger.warning("Réservation du budget speedtest échouée : %s", e)

            with contextlib.suppress(Exception):
                if self._daily_budget:
                    await client.decrby(day_key, size)
                if self._per_ip_budget:
                    await client.decrby(ip_key, size)

            await self._release_slot(client)

            return SpeedtestStart(ok=False, http=503, error="err_busy")

        rid = secrets.token_urlsafe(8)
        reservation_key = redis_keys.speedtest_reserved(token, rid)
        try:
            await client.hset(reservation_key, mapping={
                "file_id": file_id,
                "size": str(size),
                "ip_hash": ip_hash,
                "day": day,
                "ts": str(time.time()),
            })
            await client.expire(reservation_key, SPEEDTEST_RESERVATION_TTL)
        except Exception as e:
            self._logger.warning("Stockage de la réservation speedtest échoué : %s", e)

            with contextlib.suppress(Exception):
                if self._daily_budget:
                    await client.decrby(day_key, size)
                if self._per_ip_budget:
                    await client.decrby(ip_key, size)

            await self._release_slot(client)

            return SpeedtestStart(ok=False, http=503, error="err_busy")

        accel_uri = f"{self._xaccel_prefix}/{token}/{rid}/{file_id}.bin"
        return SpeedtestStart(ok=True, accel_uri=accel_uri)

    async def finalize(self, token: str, rid: str, file_id: str, bytes_sent: int, status: int) -> None:
        """
        Ajuste les compteurs Redis et journalise après envoi du fichier par nginx.

        Parameters:
            token (str): token CLI ayant servi à la réservation.
            rid (str): identifiant de la réservation.
            file_id (str): identifiant du fichier, conservé pour cohérence (déjà connu).
            bytes_sent (int): nombre d'octets effectivement envoyés par nginx ($bytes_sent).
            status (int): statut HTTP final côté nginx (200 OK, 499 client closed, etc.).
        """
        if not self._enabled:
            return

        client = redis.Redis(connection_pool=self._pool)
        key = redis_keys.speedtest_reserved(token, rid)

        try:
            data = await client.hgetall(key)
        except Exception as e:
            self._logger.warning("Lecture de la réservation speedtest échouée : %s", e)
            return

        if not data:
            # Déjà finalisée (post_action rappelée) ou nettoyée par le GC.
            return

        try:
            reserved_size = int(data.get("size", "0"))
            ip_hash = str(data.get("ip_hash", ""))
            day = str(data.get("day") or self._today())
            ts = float(data.get("ts", "0"))
            reserved_file = str(data.get("file_id", file_id))
        except (TypeError, ValueError):
            self._logger.warning("Réservation speedtest corrompue : %s", data)
            with contextlib.suppress(Exception):
                await client.delete(key)
            await self._release_slot(client)
            return

        sent = max(0, int(bytes_sent))
        refund = max(0, reserved_size - sent)
        duration_ms = max(0, int((time.time() - ts) * 1000)) if ts > 0 else 0

        if refund > 0:
            with contextlib.suppress(Exception):
                if self._daily_budget:
                    await client.decrby(redis_keys.speedtest_bytes_day(day), refund)
                if self._per_ip_budget:
                    await client.decrby(redis_keys.speedtest_bytes_ip(ip_hash, day), refund)

        await self._release_slot(client)

        with contextlib.suppress(Exception):
            await client.delete(key)

        log_status = "ok" if status == 200 and sent >= reserved_size else "killed"
        await self._query_log.create(
            node_id="local",
            command_type="speedtest",
            target=reserved_file,
            family=None,
            source_ip_hash=ip_hash,
            status=log_status,
            exit_code=None,
            duration_ms=duration_ms,
            bytes_served=sent,
            session_id=token,
        )

    async def gc_orphaned_reservations(self) -> int:
        """
        Nettoie les réservations dont le finalize n'a jamais été rappelé.

        Returns:
            int: nombre de réservations nettoyées sur ce passage.
        """
        if not self._enabled:
            return 0

        client = redis.Redis(connection_pool=self._pool)
        now = time.time()
        cleaned = 0

        try:
            async for key in client.scan_iter(match=redis_keys.speedtest_reserved_match(), count=200):
                try:
                    data = await client.hgetall(key)
                except Exception as e:
                    self._logger.debug("GC speedtest : HGETALL échoué sur %s (%s)", key, e)
                    continue
                if not data:
                    continue

                try:
                    ts = float(data.get("ts", "0"))
                except (TypeError, ValueError):
                    ts = 0.0

                if now - ts < SPEEDTEST_RESERVATION_GC_AGE:
                    continue

                try:
                    reserved_size = int(data.get("size", "0"))
                    ip_hash = str(data.get("ip_hash", ""))
                    day = str(data.get("day") or self._today())
                    file_id = str(data.get("file_id", ""))
                except (TypeError, ValueError):
                    with contextlib.suppress(Exception):
                        await client.delete(key)
                    continue

                parts = key.split(":")
                token = parts[3] if len(parts) >= 5 else None

                with contextlib.suppress(Exception):
                    if self._daily_budget and reserved_size:
                        await client.decrby(redis_keys.speedtest_bytes_day(day), reserved_size)
                    if self._per_ip_budget and reserved_size:
                        await client.decrby(redis_keys.speedtest_bytes_ip(ip_hash, day), reserved_size)

                await self._release_slot(client)

                with contextlib.suppress(Exception):
                    await client.delete(key)

                duration_ms = max(0, int((now - ts) * 1000)) if ts > 0 else 0
                await self._query_log.create(
                    node_id="local",
                    command_type="speedtest",
                    target=file_id,
                    family=None,
                    source_ip_hash=ip_hash,
                    status="orphaned",
                    exit_code=None,
                    duration_ms=duration_ms,
                    bytes_served=0,
                    session_id=token,
                )
                cleaned += 1
        except Exception as e:
            self._logger.warning("GC des réservations speedtest échoué : %s", e)

        if cleaned:
            self._logger.info("Speedtest GC : %d réservation(s) orpheline(s) nettoyée(s)", cleaned)

        return cleaned

    async def _release_slot(self, client: redis.Redis) -> None:
        """
        Décrémente le compteur de concurrence speedtest dans Redis (best-effort).

        Parameters:
            client (redis.Redis): client Redis actif.
        """
        with contextlib.suppress(Exception):
            value = await client.decr(redis_keys.speedtest_concurrency())
            if value < 0:
                await client.set(redis_keys.speedtest_concurrency(), 0)
