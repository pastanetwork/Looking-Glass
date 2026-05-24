from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from modules.utility.masking import classify_target, mask_target

if TYPE_CHECKING:
    import logging

    from modules.repositories.query_log_repo import QueryLogRepository


_ACTIVITY_DAYS = 14


class StatsService:
    def __init__(self, query_log: QueryLogRepository, logger: logging.Logger) -> None:
        self._query_log = query_log
        self._logger = logger

    async def overview(self) -> dict:
        """
        Retourne les agrégats pour la page de statistiques.

        Returns:
            dict: total, last_24h, avg_duration_ms, success_rate, by_tool, by_status, activity,
            recent et speedtest.
        """
        total = await self._query_log.count_total()
        by_status = await self._query_log.counts_by_status()
        ok = by_status.get("ok", 0)

        recent = await self._query_log.recent(limit=20)
        for entry in recent:
            raw_target = entry.get("target") or ""
            if entry.get("command_type") == "speedtest":
                entry["target_kind"] = None
                entry["suspect"] = False
                entry["target"] = raw_target
                continue
            kind = classify_target(raw_target)
            entry["target_kind"] = kind
            entry["suspect"] = kind is None and bool(raw_target)
            entry["target"] = "" if kind else mask_target(raw_target)

        return {
            "total": total,
            "last_24h": await self._query_log.count_last_24h(),
            "avg_duration_ms": await self._query_log.avg_duration_ms(),
            "success_rate": round(ok / total * 100, 1) if total else 0.0,
            "by_tool": await self._query_log.counts_by_tool(),
            "by_status": by_status,
            "activity": await self._activity(),
            "recent": recent,
            "speedtest": await self._speedtest(),
        }

    async def _speedtest(self) -> dict:
        """
        Calcule les agrégats des tests de débit pour la page de statistiques.

        Returns:
            dict: count, count_24h, total_bytes, avg_mbps et interrupt_rate.
        """
        st = await self._query_log.speedtest_stats()
        count = st.get("count", 0)
        ok_duration = st.get("ok_duration_ms", 0)
        return {
            "count": count,
            "count_24h": st.get("count_24h", 0),
            "total_bytes": st.get("total_bytes", 0),
            "avg_mbps": round(st.get("ok_bytes", 0) * 8 / ok_duration / 1000, 1) if ok_duration else 0.0,
            "interrupt_rate": round(st.get("interrupted", 0) / count * 100, 1) if count else 0.0,
        }

    async def _activity(self) -> list[dict]:
        """
        Construit la série d'activité quotidienne, jours sans requête inclus.

        Returns:
            list[dict]: liste ordonnée de dictionnaires date / count.
        """
        raw = await self._query_log.counts_by_day(days=_ACTIVITY_DAYS)
        today = datetime.now(UTC).date()
        series = []
        for offset in range(_ACTIVITY_DAYS - 1, -1, -1):
            day = (today - timedelta(days=offset)).isoformat()
            series.append({"date": day, "count": raw.get(day, 0)})
        return series
