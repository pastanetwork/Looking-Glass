from __future__ import annotations

import orjson


def format_event(event: str, data: dict) -> str:
    """
    Formate un message Server-Sent Event avec un type et des données JSON.

    Parameters:
        event (str): nom du type d'événement SSE.
        data (dict): données à sérialiser en JSON dans le champ "data".

    Returns:
        str: message SSE conforme au format "event: ...\\ndata: ...\\n\\n".
    """
    payload = orjson.dumps(data).decode()
    return f"event: {event}\ndata: {payload}\n\n"
