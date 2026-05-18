from __future__ import annotations

from typing import Optional

from modules.executors.commands.base import CommandSpec
from modules.executors.commands.dns import DigCommand
from modules.executors.commands.mtr import MtrCommand
from modules.executors.commands.ping import PingCommand
from modules.executors.commands.traceroute import TracerouteCommand
from modules.models.enums import CommandType

_SPECS: dict[CommandType, type[CommandSpec]] = {
    CommandType.PING: PingCommand,
    CommandType.TRACEROUTE: TracerouteCommand,
    CommandType.MTR: MtrCommand,
    CommandType.DNS: DigCommand,
}


def build_command_spec(
    command_type: CommandType,
    limits: dict,
    options: Optional[dict] = None
) -> CommandSpec:
    """
    Construit la CommandSpec correspondant au type d'outil demandé.

    Parameters:
        command_type (CommandType): type de commande (PING, TRACEROUTE, MTR ou DNS).
        limits (dict): dictionnaire de limites transmis au constructeur de la spec.
        options (Optional[dict]): options propres à la requête, liées à la spec si fournies.

    Returns:
        CommandSpec: instance de la spécification prête à l'emploi.
    """
    spec_cls: Optional[type[CommandSpec]] = _SPECS.get(command_type)
    if spec_cls is None:
        raise ValueError(f"Outil non supporté : {command_type}")

    spec = spec_cls(limits)
    if options is not None:
        spec.bind_options(options)

    return spec


__all__ = [
    "CommandSpec",
    "DigCommand",
    "MtrCommand",
    "PingCommand",
    "TracerouteCommand",
    "build_command_spec",
]
