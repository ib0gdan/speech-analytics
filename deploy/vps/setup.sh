#!/usr/bin/env bash
# One-shot deploy for a fresh Ubuntu droplet (DigitalOcean / Hetzner / any VPS).
# Usage on the server (as root):
#   export GROQ_API_KEY=gsk_your_key
#   curl -fsSL https://raw.githubusercontent.com/ib0gdan/speech-analytics/main/deploy/vps/setup.sh | bash
set -euo pipefail

REPO="https://github.com/ib0gdan/speech-analytics"
APP_DIR="/opt/mtbank"

if [ -z "${GROQ_API_KEY:-}" ]; then
  echo "ERROR: export GROQ_API_KEY=gsk_... before running this script." >&2
  exit 1
fi

echo "[1/5] Installing Docker (if missing)..."
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

echo "[2/5] Fetching the project..."
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone --depth 1 "$REPO" "$APP_DIR"
fi
cd "$APP_DIR"

echo "[3/5] Detecting public IP -> sslip.io hostname for auto-HTTPS..."
IP="$(curl -fsSL https://api.ipify.org)"
SITE_ADDRESS="${IP//./-}.sslip.io"    # e.g. 203-0-113-5.sslip.io
echo "      SITE_ADDRESS=${SITE_ADDRESS}"

echo "[4/5] Writing .env..."
cat > .env <<EOF
GROQ_API_KEY=${GROQ_API_KEY}
LLM_MODEL=${LLM_MODEL:-llama-3.3-70b-versatile}
PIPELINES_API_KEY=0p3n-w3bu!
SITE_ADDRESS=${SITE_ADDRESS}
EOF

echo "[5/5] Building & starting the stack..."
docker compose -f docker-compose.prod.yml up -d --build

echo ""
echo "======================================================================"
echo " Done. First boot takes a few minutes (image pulls + OpenWebUI init)."
echo "   Live demo:  https://${SITE_ADDRESS}"
echo "   REST:       https://${SITE_ADDRESS}/health"
echo "               https://${SITE_ADDRESS}/analyze  (POST)"
echo " Logs:  cd ${APP_DIR} && docker compose -f docker-compose.prod.yml logs -f"
echo "======================================================================"
