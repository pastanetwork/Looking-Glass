from __future__ import annotations

from ipaddress import ip_network

_ALWAYS_BLOCKED = [
    "0.0.0.0/8",           # « cet hôte » (RFC 1122)
    "127.0.0.0/8",         # loopback
    "169.254.0.0/16",      # link-local
    "100.64.0.0/10",       # CGN (RFC 6598)
    "192.0.0.0/24",        # affectations protocole IETF
    "192.0.2.0/24",        # documentation TEST-NET-1
    "198.18.0.0/15",       # benchmarking
    "198.51.100.0/24",     # documentation TEST-NET-2
    "203.0.113.0/24",      # documentation TEST-NET-3
    "240.0.0.0/4",         # réservé (ancienne classe E)
    "255.255.255.255/32",  # broadcast limité
    "::/128",              # non spécifié
    "::1/128",             # loopback
    "fe80::/10",           # link-local
    "2001:db8::/32",       # documentation
    "100::/64",            # discard-only (RFC 6666)
]

# Plages privées, bloquées seulement si targets.block_private est vrai.
_PRIVATE = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "fc00::/7",            # ULA (RFC 4193)
]

ALWAYS_BLOCKED_NETS = tuple(ip_network(n) for n in _ALWAYS_BLOCKED)
PRIVATE_NETS = tuple(ip_network(n) for n in _PRIVATE)
