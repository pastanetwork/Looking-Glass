from __future__ import annotations

import asyncio
import re
import socket
from dataclasses import dataclass
from ipaddress import (
    AddressValueError,
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
    ip_network,
)
from typing import List, Optional, Union

from modules.constants.ip_rules import ALWAYS_BLOCKED_NETS, PRIVATE_NETS
from modules.constants.limits import DNS_RESOLVE_TIMEOUT_SECONDS
from modules.constants.validation import HOSTNAME_REGEX, MAX_TARGET_LENGTH
from modules.models.enums import IpFamily

_IPAddress = Union[IPv4Address, IPv6Address]
_IPNetwork = Union[IPv4Network, IPv6Network]
INTERNAL_HOP_PLACEHOLDER = "•••"
_IP_TOKEN_RE = re.compile(
    r"(?:\d{1,3}\.){3}\d{1,3}"
    r"|(?:[0-9A-Fa-f]{1,4}:){2,}[0-9A-Fa-f:]*"
)

@dataclass
class ValidationResult:
    ok: bool
    ip: Optional[str] = None        # IP littérale à exécuter
    family: Optional[int] = None    # 4 ou 6
    display: Optional[str] = None   # chaîne saisie par l'utilisateur
    error: Optional[str] = None     # clé i18n d'erreur en cas de rejet


def _parse_nets(cidrs: Optional[List[str]]) -> List[_IPNetwork]:
    """
    Convertit une liste de chaînes CIDR en objets réseau, en ignorant les entrées invalides.

    Parameters:
        cidrs (Optional[List[str]]): liste de chaînes CIDR (ex. ["192.168.0.0/16"]).

    Returns:
        List[_IPNetwork]: liste d'objets IPv4Network ou IPv6Network valides.
    """
    nets: List[_IPNetwork] = []
    for cidr in cidrs or []:
        try:
            nets.append(ip_network(cidr, strict=False))
        except ValueError:
            continue
    return nets


def _in_nets(ip_obj: _IPAddress, nets: List[_IPNetwork]) -> bool:
    """
    Indique si une adresse IP appartient à l'un des réseaux donnés.

    Parameters:
        ip_obj (_IPAddress): objet IPv4Address ou IPv6Address à tester.
        nets (List[_IPNetwork]): liste d'objets IPv4Network ou IPv6Network.

    Returns:
        bool: True si l'IP est dans au moins un des réseaux.
    """
    return any(ip_obj.version == net.version and ip_obj in net for net in nets)


def is_internal_ip(token: str) -> bool:
    """
    Indique si une chaîne est une IP interne (privée, réservée ou non globale).

    Parameters:
        token (str): chaîne à tester.

    Returns:
        bool: True si la chaîne est une IP qui ne doit pas être exposée publiquement.
    """
    try:
        ip_obj = ip_address(token)
    except ValueError:
        return False
    if _in_nets(ip_obj, ALWAYS_BLOCKED_NETS) or _in_nets(ip_obj, PRIVATE_NETS):
        return True
    return not ip_obj.is_global


def redact_internal_ips(line: str) -> str:
    """
    Masque les IP internes (sauts privés/réservés) dans une ligne de sortie.

    Parameters:
        line (str): ligne de sortie d'une commande réseau.

    Returns:
        str: ligne où chaque IP interne est remplacée par un marqueur neutre.
    """
    def _mask(match: re.Match) -> str:
        token = match.group(0)
        return INTERNAL_HOP_PLACEHOLDER if is_internal_ip(token) else token

    return _IP_TOKEN_RE.sub(_mask, line)


def _family_matches(version: int, family: IpFamily) -> bool:
    """
    Vérifie que la version d'une adresse IP correspond à la famille demandée.

    Parameters:
        version (int): version de l'adresse IP (4 ou 6).
        family (IpFamily): famille de protocole souhaitée (V4, V6 ou AUTO).

    Returns:
        bool: True si la version est compatible avec la famille.
    """
    if family == IpFamily.V4:
        return version == 4
    if family == IpFamily.V6:
        return version == 6
    return True


def check_ip(ip_obj: _IPAddress, targets_cfg: dict) -> Optional[str]:
    """
    Vérifie qu'une adresse IP est une cible autorisée selon la configuration.

    Parameters:
        ip_obj (_IPAddress): objet IPv4Address ou IPv6Address à vérifier.
        targets_cfg (dict): configuration des cibles (block_private, block_bogon, etc.).

    Returns:
        Optional[str]: clé i18n d'erreur si la cible est rejetée, None si elle est autorisée.
    """
    if ip_obj.is_multicast or ip_obj.is_unspecified:
        return "err_target"
    if _in_nets(ip_obj, ALWAYS_BLOCKED_NETS):
        return "err_target"
    if targets_cfg.get("block_private", True) and (ip_obj.is_private or _in_nets(ip_obj, PRIVATE_NETS)):
        return "err_target"
    if targets_cfg.get("block_bogon", True) and not ip_obj.is_global:
        return "err_target"
    if _in_nets(ip_obj, _parse_nets(targets_cfg.get("block_list"))):
        return "err_target"
    allow = _parse_nets(targets_cfg.get("allow_list"))
    if allow and not _in_nets(ip_obj, allow):
        return "err_target"
    return None


async def _resolve(hostname: str, family: IpFamily) -> List[_IPAddress]:
    """
    Résout un nom d'hôte en adresses IP via DNS asynchrone, avec timeout.

    Parameters:
        hostname (str): nom d'hôte à résoudre.
        family (IpFamily): famille de protocole souhaitée (filtre AF_INET / AF_INET6).

    Returns:
        List[_IPAddress]: liste d'objets IPv4Address ou IPv6Address résolus (peut être vide).
    """
    af = socket.AF_UNSPEC
    if family == IpFamily.V4:
        af = socket.AF_INET
    elif family == IpFamily.V6:
        af = socket.AF_INET6

    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(
            loop.getaddrinfo(hostname, None, family=af, type=socket.SOCK_STREAM),
            timeout=DNS_RESOLVE_TIMEOUT_SECONDS,
        )
    except (socket.gaierror, OSError, TimeoutError):
        return []

    results: List[_IPAddress] = []
    seen: set[str] = set()
    for info in infos:
        addr = info[4][0].split("%")[0]
        if addr in seen:
            continue
        seen.add(addr)
        try:
            results.append(ip_address(addr))
        except ValueError:
            continue
    return results


def validate_dns_target(raw: str, targets_cfg: dict) -> ValidationResult:
    """
    Valide une cible d'interrogation DNS sans résolution préalable.

    Parameters:
        raw (str): saisie brute de l'utilisateur (nom d'hôte ou IP).
        targets_cfg (dict): configuration des cibles (allow_list, block_list, etc.).

    Returns:
        ValidationResult: résultat avec la cible littérale à interroger, ou une clé d'erreur.
    """
    raw = (raw or "").strip()
    if not raw or len(raw) > MAX_TARGET_LENGTH:
        return ValidationResult(ok=False, error="err_target")

    try:
        ip_obj = ip_address(raw)
    except (AddressValueError, ValueError):
        ip_obj = None

    if ip_obj is not None:
        err = check_ip(ip_obj, targets_cfg)
        if err:
            return ValidationResult(ok=False, display=raw, error=err)
        return ValidationResult(ok=True, ip=str(ip_obj), family=ip_obj.version, display=raw)

    if not HOSTNAME_REGEX.match(raw):
        return ValidationResult(ok=False, display=raw, error="err_target")

    return ValidationResult(ok=True, ip=raw, family=0, display=raw)


async def validate_target(raw: str, family: IpFamily, targets_cfg: dict) -> ValidationResult:
    """
    Valide une cible réseau (IP littérale ou nom d'hôte) et retourne l'IP à exécuter.

    Parameters:
        raw (str): saisie brute de l'utilisateur (IP ou nom d'hôte).
        family (IpFamily): famille de protocole souhaitée (V4, V6 ou AUTO).
        targets_cfg (dict): configuration des cibles (allow_list, block_list, etc.).

    Returns:
        ValidationResult: résultat avec l'IP littérale à utiliser, ou une clé d'erreur.
    """
    raw = (raw or "").strip()
    if not raw or len(raw) > MAX_TARGET_LENGTH:
        return ValidationResult(ok=False, error="err_target")

    try:
        ip_obj = ip_address(raw)
    except (AddressValueError, ValueError):
        ip_obj = None

    if ip_obj is not None:
        if not _family_matches(ip_obj.version, family):
            return ValidationResult(ok=False, display=raw, error="err_target")

        err = check_ip(ip_obj, targets_cfg)
        if err:
            return ValidationResult(ok=False, display=raw, error=err)

        return ValidationResult(ok=True, ip=str(ip_obj), family=ip_obj.version, display=raw)

    if not targets_cfg.get("allow_hostnames", True):
        return ValidationResult(ok=False, display=raw, error="err_target")
    if not HOSTNAME_REGEX.match(raw):
        return ValidationResult(ok=False, display=raw, error="err_target")

    resolved = await _resolve(raw, family)
    if not resolved:
        return ValidationResult(ok=False, display=raw, error="err_target")

    for ip_obj in resolved:
        if check_ip(ip_obj, targets_cfg) is None:
            return ValidationResult(ok=True, ip=str(ip_obj), family=ip_obj.version, display=raw)

    return ValidationResult(ok=False, display=raw, error="err_target")
