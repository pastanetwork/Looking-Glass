from __future__ import annotations

from modules.executors.commands.base import CommandSpec
from modules.models.enums import CommandType
from modules.utility.system import IS_WINDOWS


class PingCommand(CommandSpec):
    command_type = CommandType.PING

    def __init__(self, limits: dict) -> None:
        super().__init__(limits)
        self.count: int = int(limits.get("count", 10))

    def binary(self) -> str:
        """
        Retourne le nom du binaire ping.

        Returns:
            str: "ping".
        """
        return "ping"

    def build_argv(self, ip: str, family: int) -> list[str]:
        """
        Construit l'argv de la commande ping pour l'IP donnée.

        Parameters:
            ip (str): adresse IP littérale déjà validée.
            family (int): famille d'adresses (4 ou 6, non utilisé par ping).

        Returns:
            list[str]: argv prêt à être passé à asyncio.create_subprocess_exec.
        """
        if IS_WINDOWS:
            return ["ping", "-n", str(self.count), "-w", str(self.timeout_seconds * 1000), ip]

        return ["stdbuf", "-oL", "ping", "-n", "-c", str(self.count), "-w", str(self.timeout_seconds), "--", ip]
