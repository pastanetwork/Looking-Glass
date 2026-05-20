from __future__ import annotations

_PREFIX = "lg"


def concurrency_global() -> str:
    """Retourne la clé Redis du compteur global de commandes en cours."""
    return f"{_PREFIX}:conc:global"


def concurrency_ip(ip_hash: str) -> str:
    """
    Retourne la clé Redis du compteur de commandes en cours pour une IP.

    Parameters:
        ip_hash (str): empreinte SHA-256 de l'adresse IP cliente.

    Returns:
        str: clé Redis du compteur de concurrence par IP.
    """
    return f"{_PREFIX}:conc:ip:{ip_hash}"


def speedtest_concurrency() -> str:
    """Retourne la clé Redis du compteur de téléchargements speedtest simultanés."""
    return f"{_PREFIX}:speed:conc"


def speedtest_bytes_day(day: str) -> str:
    """
    Retourne la clé Redis du budget d'octets speedtest pour une journée.

    Parameters:
        day (str): date au format YYYYMMDD.

    Returns:
        str: clé Redis du compteur d'octets journaliers.
    """
    return f"{_PREFIX}:speed:bytes:day:{day}"


def speedtest_cli_token(token: str) -> str:
    """
    Retourne la clé Redis d'un token de test de débit en ligne de commande.

    Parameters:
        token (str): token opaque délivré au client.

    Returns:
        str: clé Redis du token, expirant automatiquement à son TTL.
    """
    return f"{_PREFIX}:speed:cli:{token}"


def speedtest_cli_token_uses(token: str) -> str:
    """
    Retourne la clé Redis comptant le nombre d'appels begin() pour un token.

    Parameters:
        token (str): token opaque délivré au client.

    Returns:
        str: clé Redis du compteur d'utilisations.
    """
    return f"{_PREFIX}:speed:cli:{token}:uses"


def speedtest_bytes_ip(ip_hash: str, day: str) -> str:
    """
    Retourne la clé Redis du budget d'octets speedtest pour une IP sur une journée.

    Parameters:
        ip_hash (str): empreinte SHA-256 de l'adresse IP cliente.
        day (str): date au format YYYYMMDD.

    Returns:
        str: clé Redis du compteur d'octets par IP et par jour.
    """
    return f"{_PREFIX}:speed:bytes:ip:{ip_hash}:{day}"


def speedtest_reserved(token: str, rid: str) -> str:
    """
    Retourne la clé Redis d'une réservation speedtest active.

    Parameters:
        token (str): token CLI déjà validé.
        rid (str): identifiant unique de la réservation pour ce téléchargement.

    Returns:
        str: clé Redis du hash de réservation.
    """
    return f"{_PREFIX}:speed:reserved:{token}:{rid}"


def speedtest_reserved_match() -> str:
    """Retourne le motif SCAN couvrant toutes les réservations speedtest actives."""
    return f"{_PREFIX}:speed:reserved:*"
