from __future__ import annotations

from modules.executors.commands.base import CommandSpec
from modules.models.enums import CommandType


class MtrCommand(CommandSpec):
    command_type = CommandType.MTR

    def __init__(self, limits: dict) -> None:
        super().__init__(limits)
        self.report_cycles: int = int(limits.get("report_cycles", 10))

    def binary(self) -> str:
        """
        Retourne le nom du binaire mtr.

        Returns:
            str: "mtr".
        """
        return "mtr"

    def build_argv(self, ip: str, family: int) -> list[str]:
        """
        Construit l'argv de la commande MTR pour l'IP donnée (POSIX uniquement).

        Parameters:
            ip (str): adresse IP littérale déjà validée.
            family (int): famille d'adresses (4 ou 6, non utilisé ici).

        Returns:
            list[str]: argv prêt à être passé à asyncio.create_subprocess_exec.
        """
        return ["mtr", "-n", "--report", "--report-wide", "--report-cycles", str(self.report_cycles), "--", ip]
