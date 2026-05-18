from __future__ import annotations

from typing import TYPE_CHECKING

from quart import render_template

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue

    from modules.executors.registry import NodeRegistry


async def render_home(config: dict) -> ResponseReturnValue:
    registry: NodeRegistry = config["node_registry"]
    nodes = [
        {
            "id": executor.node_id,
            "label": executor.label,
            "location": executor.location,
            "tools": executor.tools,
        }
        for executor in registry.list()
    ]
    tools = nodes[0]["tools"] if nodes else ["ping", "traceroute", "mtr"]
    speedtest = config.get("speedtest", {})

    return await render_template(
        "home.html",
        nodes=nodes,
        tools=tools,
        turnstile_site_key=config["turnstile"]["site_key"],
        speedtest_enabled=bool(speedtest.get("enabled", False)),
        speedtest_files=speedtest.get("files", []),
    )
