from __future__ import annotations

import dataclasses
import decimal
import uuid
from datetime import date
from typing import Any, Union

import orjson
from quart.json.provider import JSONProvider


def _default(obj: Any) -> Union[str, dict]:
    """
    Sérialise les types Python non natifs pour orjson.

    Gère date (isoformat), Decimal et UUID (str), dataclasses (asdict) et
    objets Markup (__html__). Lève TypeError pour les types non supportés.

    Parameters:
        obj (Any): objet à sérialiser.

    Returns:
        Union[str, dict]: représentation JSON-compatible de l'objet.
    """
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, (decimal.Decimal, uuid.UUID)):
        return str(obj)
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    if hasattr(obj, "__html__"):
        return str(obj.__html__())
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class OrjsonProvider(JSONProvider):
    mimetype = "application/json"

    def dumps(self, obj: Any, **kwargs: Any) -> str:
        """
        Sérialise un objet Python en chaîne JSON via orjson.

        Parameters:
            obj (Any): objet à sérialiser.

        Returns:
            str: représentation JSON de l'objet.
        """
        return orjson.dumps(
            obj,
            default=_default,
            option=orjson.OPT_NON_STR_KEYS,
        ).decode()

    def loads(self, s: Union[str, bytes], **kwargs: Any) -> Any:
        """
        Désérialise une chaîne JSON en objet Python via orjson.

        Parameters:
            s (Union[str, bytes]): données JSON à désérialiser.

        Returns:
            Any: objet Python désérialisé.
        """
        return orjson.loads(s)

    def response(self, *args: Any, **kwargs: Any) -> Any:
        """
        Construit une réponse HTTP JSON à partir des arguments positionnels et nommés.

        Returns:
            Response: réponse Quart avec le corps JSON sérialisé et le bon mimetype.
        """
        obj = self._prepare_response_obj(args, kwargs)
        return self._app.response_class(
            self.dumps(obj) + "\n",
            mimetype=self.mimetype,
        )
