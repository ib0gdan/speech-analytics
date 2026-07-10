#!/usr/bin/env bash
set -e

# nginx is the single public entrypoint; on HF Spaces it MUST match app_port: 7860.
# We do NOT reuse $PORT here: the OpenWebUI base image already exports PORT=8080 for its OWN
# backend, so `${PORT:-7860}` would resolve to 8080 and nginx would fight OpenWebUI for that port.
# nginx therefore listens on SPACE_PORT (default 7860), independent of OpenWebUI's PORT.
LISTEN_PORT="${SPACE_PORT:-7860}"
sed -i "s/listen [0-9]\+;/listen ${LISTEN_PORT};/" /etc/nginx/sites-available/default
echo "[start] nginx will listen on ${LISTEN_PORT}; OpenWebUI on ${PORT:-8080}"

mkdir -p /app/backend/data /var/log/supervisor /pipelines/pipelines
chmod -R 777 /app/backend/data /pipelines /var/log/nginx /var/log/supervisor 2>/dev/null || true

echo "[start] launching OpenWebUI(${PORT:-8080}) + pipelines(9099) + api(8000) + nginx(${LISTEN_PORT})"
exec supervisord -c /etc/supervisor/conf.d/mtbank.conf
