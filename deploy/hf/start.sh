#!/usr/bin/env bash
set -e

# HF Spaces injects secrets as env vars (e.g. GROQ_API_KEY). They are already visible to
# child processes started by supervisor. Ensure writable runtime dirs exist.
mkdir -p /app/backend/data /var/log/supervisor /pipelines/pipelines
chmod -R 777 /app/backend/data /pipelines /var/log/nginx /var/log/supervisor 2>/dev/null || true

echo "[start] launching OpenWebUI(8080) + pipelines(9099) + api(8000) + nginx(7860)"
exec supervisord -c /etc/supervisor/conf.d/mtbank.conf
