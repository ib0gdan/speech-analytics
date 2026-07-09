#!/usr/bin/env bash
set -e

# Platforms differ on which port the container must listen on:
#   - HF Spaces / local: 7860
#   - Render / Cloud Run: injected via $PORT
# nginx has no native env interpolation, so patch the listen directive at boot.
LISTEN_PORT="${PORT:-7860}"
sed -i "s/listen [0-9]\+;/listen ${LISTEN_PORT};/" /etc/nginx/sites-available/default
echo "[start] nginx will listen on ${LISTEN_PORT}"

mkdir -p /app/backend/data /var/log/supervisor /pipelines/pipelines
chmod -R 777 /app/backend/data /pipelines /var/log/nginx /var/log/supervisor 2>/dev/null || true

echo "[start] launching OpenWebUI(8080) + pipelines(9099) + api(8000) + nginx(${LISTEN_PORT})"
exec supervisord -c /etc/supervisor/conf.d/mtbank.conf
