from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    import logging

    import aiosqlite


class QueryLogRepository:
    def __init__(self, db: aiosqlite.Connection, logger: logging.Logger) -> None:
        self._db = db
        self._logger = logger

    async def create(
        self,
        *,
        node_id: str,
        command_type: str,
        target: str,
        family: Optional[int],
        source_ip_hash: str,
        status: str,
        exit_code: Optional[int],
        duration_ms: Optional[int],
        bytes_served: Optional[int] = None,
    ) -> None:
        """
        Enregistre une entrée dans le journal des requêtes (best-effort).

        Parameters:
            node_id (str): identifiant du nœud ayant traité la requête.
            command_type (str): type de commande exécutée (ping, traceroute, mtr, speedtest).
            target (str): cible affichable de la commande.
            family (Optional[int]): famille d'adresse IP (4 ou 6), ou None.
            source_ip_hash (str): empreinte hachée de l'IP source.
            status (str): statut de la requête (ok, rejected, timeout, error, killed, running).
            exit_code (Optional[int]): code de retour du processus, ou None.
            duration_ms (Optional[int]): durée d'exécution en millisecondes, ou None.
            bytes_served (Optional[int]): octets servis, renseigné pour le speedtest uniquement.
        """
        try:
            await self._db.execute(
                "INSERT INTO query_log "
                "(node_id, command_type, target, family, source_ip_hash, status, exit_code, "
                "duration_ms, bytes_served) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (node_id, command_type, target, family, source_ip_hash, status, exit_code,
                 duration_ms, bytes_served),
            )
            await self._db.commit()
        except Exception as e:
            self._logger.error("Écriture du journal échouée : %s", e)

    async def cleanup_old_entries(self, retention_days: int) -> int:
        """
        Supprime les entrées du journal plus anciennes que la période de rétention.

        Parameters:
            retention_days (int): nombre de jours de conservation des entrées.

        Returns:
            int: nombre de lignes supprimées.
        """
        cursor = await self._db.execute(
            "DELETE FROM query_log WHERE created_at < datetime('now', ?)",
            (f"-{int(retention_days)} days",),
        )
        await self._db.commit()
        return cursor.rowcount

    async def count_total(self) -> int:
        """
        Retourne le nombre total de requêtes enregistrées dans le journal.

        Returns:
            int: nombre total d'entrées.
        """
        cursor = await self._db.execute("SELECT COUNT(*) AS n FROM query_log")
        row = await cursor.fetchone()
        return row["n"] if row else 0

    async def count_last_24h(self) -> int:
        """
        Retourne le nombre de requêtes enregistrées au cours des dernières 24 heures.

        Returns:
            int: nombre d'entrées des dernières 24 heures.
        """
        cursor = await self._db.execute(
            "SELECT COUNT(*) AS n FROM query_log WHERE created_at >= datetime('now', '-1 day')"
        )
        row = await cursor.fetchone()
        return row["n"] if row else 0

    async def counts_by_tool(self) -> dict[str, int]:
        """
        Retourne la répartition du nombre de requêtes par outil.

        Returns:
            dict: dictionnaire dont les clés sont les types de commande et les valeurs les comptages.
        """
        cursor = await self._db.execute(
            "SELECT command_type AS k, COUNT(*) AS n FROM query_log GROUP BY command_type"
        )
        return {row["k"]: row["n"] for row in await cursor.fetchall()}

    async def avg_duration_ms(self) -> Optional[int]:
        """
        Retourne la durée moyenne des requêtes terminées avec succès.

        Returns:
            Optional[int]: durée moyenne en millisecondes, ou None si aucune requête réussie.
        """
        cursor = await self._db.execute(
            "SELECT AVG(duration_ms) AS a FROM query_log "
            "WHERE status = 'ok' AND duration_ms IS NOT NULL AND command_type != 'speedtest'"
        )
        row = await cursor.fetchone()
        return int(row["a"]) if row and row["a"] is not None else None

    async def speedtest_stats(self) -> dict:
        """
        Retourne les agrégats propres aux tests de débit.

        Returns:
            dict: count, count_24h, total_bytes, interrupted, ok_bytes et ok_duration_ms.
        """
        cursor = await self._db.execute(
            "SELECT "
            "COUNT(*) AS count, "
            "COALESCE(SUM(bytes_served), 0) AS total_bytes, "
            "COALESCE(SUM(CASE WHEN created_at >= datetime('now', '-1 day') THEN 1 ELSE 0 END), 0) AS count_24h, "
            "COALESCE(SUM(CASE WHEN status != 'ok' THEN 1 ELSE 0 END), 0) AS interrupted, "
            "COALESCE(SUM(CASE WHEN status = 'ok' THEN bytes_served ELSE 0 END), 0) AS ok_bytes, "
            "COALESCE(SUM(CASE WHEN status = 'ok' THEN duration_ms ELSE 0 END), 0) AS ok_duration_ms "
            "FROM query_log WHERE command_type = 'speedtest'"
        )
        row = await cursor.fetchone()
        return dict(row) if row else {}

    async def counts_by_day(self, days: int) -> dict[str, int]:
        """
        Retourne le nombre de requêtes par jour sur la période demandée.

        Parameters:
            days (int): profondeur de l'historique en jours.

        Returns:
            dict: dictionnaire date (YYYY-MM-DD) -> nombre de requêtes.
        """
        cursor = await self._db.execute(
            "SELECT date(created_at) AS d, COUNT(*) AS n FROM query_log "
            "WHERE created_at >= datetime('now', ?) GROUP BY d",
            (f"-{int(days)} days",),
        )
        return {row["d"]: row["n"] for row in await cursor.fetchall()}

    async def counts_by_status(self) -> dict[str, int]:
        """
        Retourne la répartition du nombre de requêtes par statut.

        Returns:
            dict: dictionnaire dont les clés sont les statuts et les valeurs les comptages.
        """
        cursor = await self._db.execute(
            "SELECT status AS k, COUNT(*) AS n FROM query_log GROUP BY status"
        )
        return {row["k"]: row["n"] for row in await cursor.fetchall()}

    async def recent(self, limit: int = 20) -> List[dict]:
        """
        Retourne les dernières requêtes journalisées, triées par ordre décroissant d'insertion.

        Parameters:
            limit (int): nombre maximum d'entrées à retourner (défaut : 20).

        Returns:
            List[dict]: liste de dictionnaires représentant les entrées du journal.
        """
        cursor = await self._db.execute(
            "SELECT command_type, target, family, status, duration_ms, created_at "
            "FROM query_log ORDER BY id DESC LIMIT ?",
            (int(limit),),
        )
        return [dict(row) for row in await cursor.fetchall()]
