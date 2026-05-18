from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from modules.executors.commands import build_command_spec
from modules.executors.local import LocalExecutor
from modules.models.enums import CommandType

if TYPE_CHECKING:
    import logging

    from modules.executors.base import NodeExecutor


class NodeRegistry:
    def __init__(self, nodes_config: List[dict], limits: dict, logger: logging.Logger) -> None:
        self._logger: logging.Logger = logger
        self._executors: dict[str, NodeExecutor] = {}
        self._order: List[str] = []
        for node in nodes_config:
            node_type: str = node.get("type", "local")
            if node_type == "local":
                executor: NodeExecutor = LocalExecutor(node, logger)
            else:
                logger.warning("Type de nœud inconnu, ignoré : %s", node_type)
                continue
            executor.tools = self._available_tools(executor, executor.tools, limits)
            self._executors[executor.node_id] = executor
            self._order.append(executor.node_id)

    def _available_tools(self, executor: NodeExecutor, tools: List[str], limits: dict) -> List[str]:
        """
        Filtre les outils d'un nœud pour ne conserver que ceux dont le binaire
        est installé sur ce nœud.

        Parameters:
            executor (NodeExecutor): exécuteur du nœud à interroger.
            tools (List[str]): outils déclarés dans la configuration du nœud.
            limits (dict): limites par outil, requises pour résoudre le binaire.

        Returns:
            List[str]: sous-ensemble des outils réellement disponibles.
        """
        available: List[str] = []
        for tool in tools:
            try:
                spec = build_command_spec(CommandType(tool), limits[tool])
            except (ValueError, KeyError):
                self._logger.warning(
                    "Outil « %s » non reconnu ou sans limites configurées, masqué", tool
                )
                continue
            if executor.tool_available(spec.binary()):
                available.append(tool)
            else:
                self._logger.info(
                    "Outil « %s » indisponible sur le nœud %s, masqué", tool, executor.node_id
                )
        return available

    def get(self, node_id: str) -> Optional[NodeExecutor]:
        """
        Retourne l'exécuteur du nœud correspondant à l'identifiant.

        Parameters:
            node_id (str): identifiant du nœud.

        Returns:
            Optional[NodeExecutor]: l'exécuteur, ou None si l'identifiant est inconnu.
        """
        return self._executors.get(node_id)

    def list(self) -> List[NodeExecutor]:
        """
        Retourne tous les exécuteurs dans l'ordre de la configuration.

        Returns:
            List[NodeExecutor]: liste ordonnée des exécuteurs de nœuds.
        """
        return [self._executors[node_id] for node_id in self._order]

    async def aclose_all(self) -> None:
        """Ferme tous les nœuds."""
        for executor in self._executors.values():
            try:
                await executor.aclose()
            except Exception as e:
                self._logger.warning("Fermeture du nœud %s échouée : %s", executor.node_id, e)
