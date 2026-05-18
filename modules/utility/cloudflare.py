from __future__ import annotations

from ipaddress import ip_network
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    import logging

_CLOUDFLARE_IP_URLS = (
    "https://www.cloudflare.com/ips-v4",
    "https://www.cloudflare.com/ips-v6",
)
_FETCH_TIMEOUT_SECONDS = 10


async def fetch_cloudflare_nets(logger: logging.Logger) -> list:
    """
    Récupère les plages IP officielles de Cloudflare en IPv4 et IPv6.

    Parameters:
        logger (logging.Logger): logger applicatif pour les avertissements.

    Returns:
        list[_IPNetwork]: plages récupérées, ou liste vide en cas d'échec
        (l'appelant conserve alors la liste intégrée de repli).
    """
    nets: list = []
    try:
        async with aiohttp.ClientSession() as session:
            for url in _CLOUDFLARE_IP_URLS:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=_FETCH_TIMEOUT_SECONDS)) as resp:
                    if resp.status != 200:
                        logger.warning("Plages Cloudflare : %s a répondu %s", url, resp.status)
                        return []

                    text = await resp.text()
                    for line in text.splitlines():
                        cidr = line.strip()
                        if not cidr:
                            continue
                        try:
                            nets.append(ip_network(cidr))
                        except ValueError:
                            logger.warning("Plage Cloudflare ignorée (CIDR invalide) : %s", cidr)
    except Exception as e:
        logger.warning("Récupération des plages Cloudflare échouée : %s", e)
        return []

    return nets
