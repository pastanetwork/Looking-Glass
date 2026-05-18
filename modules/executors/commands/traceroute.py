from __future__ import annotations

from modules.executors.commands.base import CommandSpec
from modules.models.enums import CommandType
from modules.utility.system import IS_WINDOWS


class TracerouteCommand(CommandSpec):
    command_type = CommandType.TRACEROUTE

    def __init__(self, limits: dict) -> None:
        super().__init__(limits)
        self.max_hops: int = int(limits.get("max_hops", 30))

    def binary(self) -> str:
        """
        Retourne le nom du binaire de traceroute selon la plateforme.

        Returns:
            str: "tracert" sous Windows, "traceroute" sous POSIX.
        """
        return "tracert" if IS_WINDOWS else "traceroute"

    def build_argv(self, ip: str, family: int) -> list[str]:
        """
        Construit l'argv de la commande traceroute pour l'IP donnée.

        Parameters:
            ip (str): adresse IP littérale déjà validée.
            family (int): famille d'adresses (4 ou 6, non utilisé par traceroute).

        Returns:
            list[str]: argv prêt à être passé à asyncio.create_subprocess_exec.
        """
        if IS_WINDOWS:
            return ["tracert", "-d", "-h", str(self.max_hops), ip]

        return ["stdbuf", "-oL", "traceroute", "-n", "-q", "2", "-w", "2", "-m", str(self.max_hops), "--", ip]
