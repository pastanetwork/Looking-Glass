from __future__ import annotations

from typing import TYPE_CHECKING

from quart import jsonify

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue

    from modules.executors.registry import NodeRegistry


async def list_nodes_func(config: dict) -> ResponseReturnValue:
    """
    Retourne la liste des nœuds disponibles.

    Parameters:
        config (dict): configuration de l'application (node_registry).
    """
    registry: NodeRegistry = config["node_registry"]
    nodes = [
        {
            "id": executor.node_id,
            "label": executor.label,
            "location": executor.location,
            "ipv4": executor.ipv4_enabled,
            "ipv6": executor.ipv6_enabled,
            "tools": executor.tools,
        }
        for executor in registry.list()
    ]
    return jsonify({"status": "Ok", "status_code": 200, "data": {"nodes": nodes}})
