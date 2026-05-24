from __future__ import annotations

import re
from ipaddress import ip_address
from typing import Optional

_MASK = "•••"
_IPV4_RE = re.compile(r"(?:\d{1,3}\.){3}\d{1,3}")
_SAFE_TARGET_RE = re.compile(r"^[A-Za-z0-9.:_-]+$")


def _mask_ipv4(match: re.Match[str]) -> str:
    """Masque le dernier octet d'une IPv4 repérée dans une chaîne."""
    value = match.group()
    try:
        ip_address(value)
    except ValueError:
        return value
    return ".".join(value.split(".")[:3]) + "." + _MASK


def mask_target(value: str) -> str:
    """
    Masque une cible avant affichage public pour ne pas exposer d'IP complète.

    Parameters:
        value (str): cible brute issue du journal des requêtes.

    Returns:
        str: cible masquée, sûre à afficher publiquement.
    """
    try:
        ip = ip_address(value.strip())
    except ValueError:
        return _IPV4_RE.sub(_mask_ipv4, value)
    if ip.version == 4:
        return ".".join(value.strip().split(".")[:3]) + "." + _MASK
    return ":".join(ip.exploded.split(":")[:4]) + ":" + _MASK


def classify_target(value: str) -> Optional[str]:
    """
    Classe une cible en famille générique pour un affichage public anonymisé.

    Parameters:
        value (str): cible brute issue du journal des requêtes.

    Returns:
        Optional[str]: "ipv4", "ipv6", "domain" ou None si la cible est vide ou suspecte.
    """
    stripped = value.strip()
    if not stripped or _SAFE_TARGET_RE.match(stripped) is None:
        return None
    try:
        ip = ip_address(stripped)
    except ValueError:
        return "domain"
    return "ipv4" if ip.version == 4 else "ipv6"


def is_suspicious_target(value: str) -> bool:
    """
    Indique si une cible contient des caractères étrangers à une IP ou un nom d'hôte.

    Parameters:
        value (str): cible brute issue du journal des requêtes.

    Returns:
        bool: True si la cible paraît malveillante.
    """
    return bool(value) and _SAFE_TARGET_RE.match(value) is None
