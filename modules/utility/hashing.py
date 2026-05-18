from __future__ import annotations

import hashlib


def hash_ip(ip: str, salt: str) -> str:
    """
    Hache une adresse IP source avec SHA-256 et le sel de configuration.

    Parameters:
        ip (str): adresse IP du client.
        salt (str): sel secret issu de la configuration.

    Returns:
        str: empreinte hexadécimale SHA-256 de l'IP salée.
    """
    return hashlib.sha256((salt + (ip or "")).encode("utf-8")).hexdigest()
