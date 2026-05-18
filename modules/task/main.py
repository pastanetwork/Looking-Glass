from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Optional

from modules.constants.limits import (
    CLEANUP_ERROR_DELAY_SECONDS,
    CLEANUP_INITIAL_DELAY_SECONDS,
    CLEANUP_INTERVAL_SECONDS,
)

if TYPE_CHECKING:
    import logging

    from modules.repositories.query_log_repo import QueryLogRepository


class TaskMain:
    def __init__(self, config: dict) -> None:
        self._config = config
        self._logger: logging.Logger = config["logger"]
        self._tasks: dict[str, dict[str, Any]] = {
            "cleanup": {"start": False, "task": None},
        }

    async def start(self) -> None:
        """Démarre les tâches de fond."""
        if not self._tasks["cleanup"]["start"] and self._tasks["cleanup"]["task"] is None:
            self._tasks["cleanup"]["start"] = True
            self._tasks["cleanup"]["task"] = asyncio.create_task(self._cleanup_task())
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
