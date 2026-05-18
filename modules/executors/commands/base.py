from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.models.enums import CommandType


class CommandSpec(ABC):
    command_type: CommandType

    def __init__(self, limits: dict) -> None:
        self.timeout_seconds: int = int(limits["timeout_seconds"])
        self.max_lines: int = int(limits["max_lines"])
        self.max_bytes: int = int(limits["max_bytes"])

    @abstractmethod
    def binary(self) -> str:
        """
        Retourne le nom du binaire requis pour cette commande.

        Returns:
            str: nom du binaire à rechercher dans le PATH.
        """

    @abstractmethod
    def build_argv(self, ip: str, family: int) -> list[str]:
        """
        Construit la liste d'arguments du sous-processus pour l'IP donnée.

        Parameters:
            ip (str): adresse IP littérale déjà validée.
            family (int): famille d'adresses (4 ou 6).

        Returns:
            list[str]: argv prêt à être passé à asyncio.create_subprocess_exec.
        """

    def filter_line(self, line: str) -> str:
        """
        Transforme une ligne de sortie avant diffusion (identité par défaut).

        Parameters:
            line (str): ligne de sortie brute du sous-processus.

        Returns:
            str: ligne éventuellement transformée.
        """
        return line
