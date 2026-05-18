#!/bin/bash
set -e

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
