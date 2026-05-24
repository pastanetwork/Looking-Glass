#!/bin/bash
set -e

apply_firewall() {
    local v4_nets=(
        "10.0.0.0/8"           # RFC 1918 privé
        "172.16.0.0/12"        # RFC 1918 privé
        "192.168.0.0/16"       # RFC 1918 privé
        "169.254.0.0/16"       # link-local
        "127.0.0.0/8"          # loopback
        "0.0.0.0/8"            # « cet hôte » (RFC 1122)
        "100.64.0.0/10"        # CGN (RFC 6598)
        "192.0.0.0/24"         # affectations protocole IETF
        "192.0.2.0/24"         # documentation TEST-NET-1
        "198.18.0.0/15"        # benchmarking
        "198.51.100.0/24"      # documentation TEST-NET-2
        "203.0.113.0/24"       # documentation TEST-NET-3
        "240.0.0.0/4"          # réservé (ancienne classe E)
    )
    local v6_nets=(
        "fc00::/7"             # ULA (RFC 4193)
        "fe80::/10"            # link-local
        "::1/128"              # loopback
        "::/128"               # non spécifié
        "2001:db8::/32"        # documentation
        "100::/64"             # discard-only (RFC 6666)
    )

    iptables -I OUTPUT 1 -o lo -j ACCEPT
    iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    for net in "${v4_nets[@]}"; do
        iptables -A OUTPUT -d "$net" -j REJECT
    done

    if command -v ip6tables >/dev/null 2>&1; then
        ip6tables -I OUTPUT 1 -o lo -j ACCEPT 2>/dev/null || true
        ip6tables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || true
        for net in "${v6_nets[@]}"; do
            ip6tables -A OUTPUT -d "$net" -j REJECT 2>/dev/null || true
        done
    fi
}

if [ "$(id -u)" = "0" ]; then
    if command -v iptables >/dev/null 2>&1; then
        if apply_firewall; then
            echo "[entrypoint] Pare-feu iptables appliqué (RFC1918 bloqué en sortie)."
        else
            echo "[entrypoint] Avertissement : pose du pare-feu iptables échouée." >&2
        fi
    else
        echo "[entrypoint] Avertissement : iptables absent, pare-feu non appliqué." >&2
    fi

    exec setpriv \
        --reuid=lguser --regid=lguser --init-groups \
        --bounding-set=-net_admin,-setuid,-setgid,-setpcap \
        --inh-caps=-all \
        "$0" "$@"
fi

if [ -z "${REDIS_PASSWORD}" ]; then
    REDIS_PASSWORD="$(python -c 'import secrets; print(secrets.token_hex(24))')"
fi
export REDIS_PASSWORD

redis-server /app/redis.conf --requirepass "${REDIS_PASSWORD}" &
REDIS_PID=$!

hypercorn main:app \
    --bind "0.0.0.0:${LG_PORT:-8080}" \
    --workers "${LG_WORKERS:-4}" \
    --worker-class uvloop &
APP_PID=$!

shutdown() {
    kill -TERM "${APP_PID}" "${REDIS_PID}" 2>/dev/null || true
}
trap shutdown TERM INT

wait -n
shutdown
wait
