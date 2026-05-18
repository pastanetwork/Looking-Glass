"""Spécifications de commande et fabrique associée."""
from __future__ import annotations

from typing import Optional

from modules.executors.commands.base import CommandSpec
from modules.executors.commands.mtr import MtrCommand
from modules.executors.commands.ping import PingCommand
from modules.executors.commands.traceroute import TracerouteCommand
from modules.models.enums import CommandType

_SPECS: dict[CommandType, type[CommandSpec]] = {
    CommandType.PING: PingCommand,
    CommandType.TRACEROUTE: TracerouteCommand,
    CommandType.MTR: MtrCommand,
}


def build_command_spec(command_type: CommandType, limits: dict) -> CommandSpec:
    """
    Construit la CommandSpec correspondant au type d'outil demandé.

    Parameters:
        command_type (CommandType): type de commande (PING, TRACEROUTE ou MTR).
        limits (dict): dictionnaire de limites transmis au constructeur de la spec.

    Returns:
        CommandSpec: instance de la spécification prête à l'emploi.
    """
    spec_cls: Optional[type[CommandSpec]] = _SPECS.get(command_type)
    if spec_cls is None:
        raise ValueError(f"Outil non supporté : {command_type}")
    return spec_cls(limits)


__all__ = ["CommandSpec", "MtrCommand", "PingCommand", "TracerouteCommand", "build_command_spec"]
