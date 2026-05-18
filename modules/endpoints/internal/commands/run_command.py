from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Optional

from quart import Response, jsonify, request

from modules.models.enums import CommandStatus
from modules.utility.middleware import get_client_ip
from modules.utility.sse import format_event

if TYPE_CHECKING:
    import logging
    from collections.abc import AsyncGenerator

    from quart.typing import ResponseReturnValue

    from modules.services.command_service import CommandService, PrepareResult


async def run_command_func(config: dict) -> ResponseReturnValue:
    command_service: CommandService = config["command_service"]
    logger: logging.Logger = config["logger"]

    client_ip = get_client_ip() or ""
    payload = await request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}

    ticket = await command_service.prepare(payload, client_ip)
    if not ticket.ok:
        return jsonify({"status": "Error", "status_code": ticket.http, "detail": ticket.error}), ticket.http

    response = Response(_stream(command_service, ticket, logger), content_type="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Connection"] = "keep-alive"
    response.timeout = None

    return response


async def _stream(
    command_service: CommandService,
    ticket: PrepareResult,
    logger: logging.Logger,
) -> AsyncGenerator[str, None]:
    stream = None
    status: CommandStatus = CommandStatus.ERROR
    exit_code: Optional[int] = None
    duration_ms: Optional[int] = None

    try:
        yield format_event("meta", {
            "node": ticket.node_id,
            "tool": ticket.command_type,
            "target": ticket.display,
            "ip": ticket.ip,
            "family": ticket.family,
        })
        if ticket.executor is None or ticket.spec is None or ticket.ip is None or ticket.family is None:
            raise RuntimeError("Ticket d'exécution incomplet")
        stream = ticket.executor.run(ticket.spec, ticket.ip, ticket.family)
        async for line in stream:
            yield format_event("line", {"text": line})

        status = stream.status
        exit_code = stream.exit_code
        duration_ms = stream.duration_ms
    except asyncio.CancelledError:
        if stream is not None:
            status = CommandStatus.KILLED
            duration_ms = stream.duration_ms
        raise
    except Exception as e:
        logger.exception("Erreur de streaming : %s", e)
    finally:
        if stream is not None:
            with contextlib.suppress(Exception):
                await stream.aclose()
            if status == CommandStatus.ERROR and stream.status != CommandStatus.RUNNING:
                status = stream.status
            if duration_ms is None:
                duration_ms = stream.duration_ms

        with contextlib.suppress(Exception):
            await asyncio.shield(command_service.finalize(ticket, status, exit_code, duration_ms))

    yield format_event("end", {"status": status.value, "exit_code": exit_code, "duration_ms": duration_ms})
