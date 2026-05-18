from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import signal
import subprocess
import time
from typing import TYPE_CHECKING, AsyncIterator, Optional

from modules.executors.base import NodeExecutor
from modules.models.enums import CommandStatus
from modules.utility.system import IS_WINDOWS, SUBPROCESS_OUTPUT_ENCODING

if TYPE_CHECKING:
    import logging

    from modules.executors.commands.base import CommandSpec


class LocalCommandStream:
    def __init__(self, argv: list[str], spec: CommandSpec, logger: logging.Logger) -> None:
        self._argv: list[str] = argv
        self._spec: CommandSpec = spec
        self._logger: logging.Logger = logger
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._deadline = 0.0
        self._started_at = 0.0
        self._line_count = 0
        self._byte_count = 0
        self._started = False
        self._done = False
        self._closed = False
        self.status: CommandStatus = CommandStatus.RUNNING
        self.exit_code: Optional[int] = None
        self.duration_ms: Optional[int] = None

    def __aiter__(self) -> AsyncIterator[str]:
        return self

    async def __anext__(self) -> str:
        """
        Retourne la prochaine ligne de sortie du sous-processus.

        Returns:
            str: ligne de sortie décodée en UTF-8, sans retour chariot.
        """
        if not self._started:
            await self._start()

        if self._done or self._proc is None or self._proc.stdout is None:
            raise StopAsyncIteration

        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            await self._end(CommandStatus.TIMEOUT, kill=True)
            raise StopAsyncIteration

        try:
            raw = await asyncio.wait_for(self._proc.stdout.readline(), timeout=remaining)
        except TimeoutError:
            await self._end(CommandStatus.TIMEOUT, kill=True)
            raise StopAsyncIteration from None
        except asyncio.CancelledError:
            await self._end(CommandStatus.KILLED, kill=True)
            raise

        if not raw:
            with contextlib.suppress(Exception):
                await self._proc.wait()

            self.exit_code = self._proc.returncode
            ok = self._proc.returncode == 0
            await self._end(CommandStatus.OK if ok else CommandStatus.ERROR, kill=False)

            raise StopAsyncIteration

        self._line_count += 1
        self._byte_count += len(raw)
        line = raw.decode(SUBPROCESS_OUTPUT_ENCODING, "replace").rstrip("\r\n")

        if self._line_count > self._spec.max_lines or self._byte_count > self._spec.max_bytes:
            await self._end(CommandStatus.KILLED, kill=True)
            return line

        return line

    async def _start(self) -> None:
        """Lance le sous-processus et initialise l'échéance."""
        self._started = True
        self._started_at = time.monotonic()
        self._deadline = self._started_at + self._spec.timeout_seconds

        kwargs: dict = {}
        if IS_WINDOWS:
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            kwargs["start_new_session"] = True

        try:
            self._proc = await asyncio.create_subprocess_exec(
                *self._argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                stdin=asyncio.subprocess.DEVNULL,
                **kwargs,
            )
        except (FileNotFoundError, OSError, ValueError) as e:
            self._logger.warning("Lancement de commande échoué : %s", e)
            await self._end(CommandStatus.ERROR, kill=False)

    async def _end(self, status: CommandStatus, kill: bool) -> None:
        """
        Finalise le flux en enregistrant le statut et la durée.

        Parameters:
            status (CommandStatus): statut à attribuer si le flux est encore en cours.
            kill (bool): si True, tue le processus avant de finaliser.
        """
        if self._done:
            return

        self._done = True

        if self.status == CommandStatus.RUNNING:
            self.status = status
        if kill:
            await self._kill()
        if self.duration_ms is None:
            elapsed = time.monotonic() - self._started_at if self._started_at else 0.0
            self.duration_ms = int(elapsed * 1000)

    async def _kill(self) -> None:
        """Envoie SIGKILL au groupe de processus et attend la terminaison."""
        proc = self._proc
        if proc is None or proc.returncode is not None:
            return

        try:
            if IS_WINDOWS:
                proc.kill()
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass

        with contextlib.suppress(Exception):
            await asyncio.wait_for(proc.wait(), timeout=3)

    async def aclose(self) -> None:
        """Termine le flux et tue le processus s'il tourne encore (idempotent)."""
        if self._closed:
            return

        self._closed = True
        await self._end(CommandStatus.KILLED, kill=True)


class LocalExecutor(NodeExecutor):
    async def health(self) -> bool:
        """
        Indique si le nœud local est opérationnel (toujours True).

        Returns:
            bool: True systématiquement.
        """
        return True

    def run(self, spec: CommandSpec, ip: str, family: int) -> LocalCommandStream:
        """
        Construit l'argv et retourne le flux de sortie.

        Parameters:
            spec (CommandSpec): spécification de la commande.
            ip (str): adresse IP littérale déjà validée.
            family (int): famille d'adresses (4 ou 6).

        Returns:
            LocalCommandStream: flux asynchrone prêt à être itéré.
        """
        argv: list[str] = spec.build_argv(ip, family)
        return LocalCommandStream(argv, spec, self._logger)

    def tool_available(self, binary: str) -> bool:
        """
        Indique si le binaire de l'outil est présent sur le système.

        Parameters:
            binary (str): nom du binaire à rechercher dans le PATH.

        Returns:
            bool: True si le binaire est trouvé, False sinon.
        """
        return shutil.which(binary) is not None

    async def aclose(self) -> None:
        """Aucune ressource à libérer pour le nœud local."""
        return None
