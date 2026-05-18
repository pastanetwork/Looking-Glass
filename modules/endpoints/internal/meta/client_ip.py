from __future__ import annotations

from typing import TYPE_CHECKING

from quart import jsonify

from modules.utility.middleware import get_client_ip

if TYPE_CHECKING:
    from quart.typing import ResponseReturnValue


async def client_ip_func() -> ResponseReturnValue:
    ip = get_client_ip()
    return jsonify({
        "status": "Ok",
        "status_code": 200,
        "data": {"ip": ip},
    }), 200
