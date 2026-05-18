from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, AsyncIterator, Optional, Protocol

if TYPE_CHECKING:
    import logging

    from modules.executors.commands.base import CommandSpec
    from modules.models.enums import CommandStatus


class CommandStream(Protocol):
    status: CommandStatus
    exit_code: Optional[int]
    duration_ms: Optional[int]

    def __aiter__(self) -> AsyncIterator[str]: ...

    async def aclose(self) -> None: ...


class NodeExecutor(ABC):
    def __init__(self, node_config: dict, logger: logging.Logger) -> None:
        self.node_id: str = node_config["id"]
        self.label: str = node_config.get("label", node_config["id"])
        self.location: Optional[str] = node_config.get("location")
        self.ipv4_enabled: bool = bool(node_config.get("ipv4", True))
        self.ipv6_enabled: bool = bool(node_config.get("ipv6", True))
        self.tools: list[str] = list(node_config.get("tools", ["ping", "traceroute", "mtr"]))
        self._logger: logging.Logger = logger

    @abstractmethod
    async def health(self) -> bool:
        """
        Indique si le nœud est opérationnel.

        Returns:
            bool: True si le nœud peut accepter des commandes, False sinon.
        """

    @abstractmethod
    def tool_available(self, binary: str) -> bool:
        """
        Indique si un binaire d'outil est disponible sur ce nœud.

        Parameters:
            binary (str): nom du binaire recherché.

        Returns:
            bool: True si le binaire peut être exécuté sur le nœud.
        """

    @abstractmethod
    def run(self, spec: CommandSpec, ip: str, family: int) -> CommandStream:
        """
        Démarre l'exécution d'une commande et retourne le flux de sortie.

        Parameters:
            spec (CommandSpec): spécification de la commande à exécuter.
            ip (str): adresse IP littérale déjà validée.
            family (int): famille d'adresses (4 ou 6).

        Returns:
            CommandStream: flux asynchrone des lignes de sortie.
        """

    @abstractmethod
    async def aclose(self) -> None:
        """Libère les ressources du nœud."""
