from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Optional

from modules.constants.limits import (
    CLEANUP_ERROR_DELAY_SECONDS,
    CLEANUP_INITIAL_DELAY_SECONDS,
    CLEANUP_INTERVAL_SECONDS,
    SPEEDTEST_GC_INITIAL_DELAY,
    SPEEDTEST_GC_INTERVAL,
)

if TYPE_CHECKING:
    import logging

    from modules.repositories.query_log_repo import QueryLogRepository
    from modules.services.speedtest_service import SpeedtestService


class TaskMain:
    def __init__(self, config: dict) -> None:
        self._config = config
        self._logger: logging.Logger = config["logger"]
        self._tasks: dict[str, dict[str, Any]] = {
            "cleanup": {"start": False, "task": None},
            "speedtest_gc": {"start": False, "task": None},
        }

    async def start(self) -> None:
        """Démarre les tâches de fond."""
        if not self._tasks["cleanup"]["start"] and self._tasks["cleanup"]["task"] is None:
            self._tasks["cleanup"]["start"] = True
            self._tasks["cleanup"]["task"] = asyncio.create_task(self._cleanup_task())

        speedtest_service: Optional[SpeedtestService] = self._config.get("speedtest_service")
        if speedtest_service is not None and speedtest_service.enabled and not self._tasks["speedtest_gc"]["start"] and self._tasks["speedtest_gc"]["task"] is None:
            self._tasks["speedtest_gc"]["start"] = True
            self._tasks["speedtest_gc"]["task"] = asyncio.create_task(self._speedtest_gc_task())

        self._logger.info("Système de tâches démarré")

    async def stop(self) -> None:
        """Arrête les tâches de fond."""
        for name, info in self._tasks.items():
            info["start"] = False
            task = info.get("task")
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    self._logger.warning(f"Tâche '{name}' en erreur à l'arrêt : {e}")
            info["task"] = None
        self._logger.info("Système de tâches arrêté")

    async def _cleanup_task(self) -> None:
        """Boucle de nettoyage périodique."""
        await asyncio.sleep(CLEANUP_INITIAL_DELAY_SECONDS)
        while self._tasks["cleanup"]["start"]:
            try:
                await self._run_cleanup()
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.exception(f"Erreur dans la tâche de nettoyage : {e}")
                await asyncio.sleep(CLEANUP_ERROR_DELAY_SECONDS)

    async def _run_cleanup(self) -> None:
        """Purge le journal des requêtes."""
        query_log_repo: Optional[QueryLogRepository] = self._config.get("query_log_repo")
        if query_log_repo is None:
            return

        retention = self._config.get("query_log_retention_days", 90)
        try:
            deleted = await query_log_repo.cleanup_old_entries(retention_days=retention)
            if deleted:
                self._logger.info(f"Journal : {deleted} entrée(s) purgée(s) (rétention {retention}j)")
        except Exception as e:
            self._logger.warning(f"Purge du journal échouée : {e}")

    async def _speedtest_gc_task(self) -> None:
        """Boucle GC des réservations speedtest orphelines."""
        await asyncio.sleep(SPEEDTEST_GC_INITIAL_DELAY)
        while self._tasks["speedtest_gc"]["start"]:
            try:
                await self._run_speedtest_gc()
                await asyncio.sleep(SPEEDTEST_GC_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.exception(f"Erreur dans le GC speedtest : {e}")
                await asyncio.sleep(CLEANUP_ERROR_DELAY_SECONDS)

    async def _run_speedtest_gc(self) -> None:
        """Nettoie les réservations speedtest orphelines."""
        speedtest_service: Optional[SpeedtestService] = self._config.get("speedtest_service")
        if speedtest_service is None:
            return

        try:
            await speedtest_service.gc_orphaned_reservations()
        except Exception as e:
            self._logger.warning(f"GC speedtest échoué : {e}")
