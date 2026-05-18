# syntax=docker/dockerfile:1
# Image unique de la Looking Glass : application Quart + Redis interne.

# === build des assets statiques (Node + Python) ===
FROM node:20-slim AS assets
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY tailwind.config.js ./
COPY minification ./minification
COPY templates ./templates
COPY static_dev ./static_dev
RUN python3 minification/minify.py --ci

# === runtime ===
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
        redis-server iputils-ping traceroute mtr-tiny bind9-dnsutils \
        ca-certificates git curl tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py config.example.json ./
COPY modules ./modules
COPY templates ./templates
COPY i18n ./i18n
COPY deploy/redis.conf /app/redis.conf
COPY deploy/docker-entrypoint.sh /app/deploy/docker-entrypoint.sh
COPY --from=assets /build/static ./static
RUN chmod +x /app/deploy/docker-entrypoint.sh

RUN useradd --system --uid 10001 lguser \
    && mkdir -p /app/data /app/logs /config \
    && chown -R lguser:lguser /app/data /app/logs

ENV LG_PORT=8080 \
    LG_WORKERS=4 \
    DEV=False \
    PYTHONUNBUFFERED=1

EXPOSE 8080
USER lguser

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${LG_PORT}/api/v1/health" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/app/deploy/docker-entrypoint.sh"]
