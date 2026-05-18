from __future__ import annotations

from typing import TYPE_CHECKING

from quart import render_template

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue


async def render_about(config: dict) -> ResponseReturnValue:
    return await render_template("about.html")
