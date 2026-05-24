#!/bin/bash
set -e

apply_firewall() {
    local v4_nets=(
        "10.0.0.0/8"
        "172.16.0.0/12"
        "192.168.0.0/16"
        "169.254.0.0/16"
        "127.0.0.0/8"
    )
    local v6_nets=(
        "fc00::/7"
        "fe80::/10"
        "::1/128"
    )

    iptables -I OUTPUT 1 -o lo -j ACCEPT
    for net in "${v4_nets[@]}"; do
        iptables -A OUTPUT -d "$net" -j REJECT
    done

    if command -v ip6tables >/dev/null 2>&1; then
        ip6tables -I OUTPUT 1 -o lo -j ACCEPT 2>/dev/null || true
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
        --bounding-set=-net_admin,-setuid,-setgid \
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
