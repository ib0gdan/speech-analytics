#!/usr/bin/env bash
# One-shot deploy for a fresh Ubuntu server (Timeweb / VDSina / Hetzner / DigitalOcean / any VPS).
#
# Usage on the server (as root):
#   export GROQ_API_KEY=gsk_your_key
#   curl -fsSL https://raw.githubusercontent.com/ib0gdan/speech-analytics/main/deploy/vps/setup.sh | bash
#
# Optional: WHISPER_MODEL=small|base|medium  (default is chosen from the box's RAM)
set -euo pipefail

REPO="https://github.com/ib0gdan/speech-analytics"
APP_DIR="/opt/mtbank"

if [ -z "${GROQ_API_KEY:-}" ]; then
  echo "ERROR: export GROQ_API_KEY=gsk_... before running this script." >&2
  exit 1
fi

TOTAL_MB=$(free -m | awk '/^Mem:/{print $2}')
echo "[0/6] Detected ${TOTAL_MB} MB RAM"

# Measured footprint: openwebui ~680 MiB, api ~445 MiB, pipelines ~1.1 GiB with whisper `small`
# under load => ~2.3 GiB. `base` saves ~350 MiB per process, so a 2 GB box needs it.
if [ -z "${WHISPER_MODEL:-}" ]; then
  if [ "$TOTAL_MB" -lt 3000 ]; then WHISPER_MODEL=base; else WHISPER_MODEL=small; fi
fi
echo "      WHISPER_MODEL=${WHISPER_MODEL}"

# Building the images compiles wheels and briefly needs more RAM than the services do at rest.
# Swap costs nothing on disk-backed VPS and turns an OOM-killed build into a slightly slower one.
if [ "$TOTAL_MB" -lt 4000 ] && ! swapon --show | grep -q .; then
  echo "[1/6] Adding 2 GB swap (build headroom on a small box)..."
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
else
  echo "[1/6] Swap not needed"
fi

echo "[2/6] Installing Docker (if missing)..."
command -v docker >/dev/null 2>&1 || curl -fsSL https://get.docker.com | sh

echo "[3/6] Fetching the project..."
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone --depth 1 "$REPO" "$APP_DIR"
fi
cd "$APP_DIR"

echo "[4/6] Detecting public IP -> sslip.io hostname for auto-HTTPS..."
IP="$(curl -fsSL https://api.ipify.org)"
SITE_ADDRESS="${IP//./-}.sslip.io"    # e.g. 203-0-113-5.sslip.io
echo "      SITE_ADDRESS=${SITE_ADDRESS}"

echo "[5/6] Writing .env..."
cat > .env <<EOF
GROQ_API_KEY=${GROQ_API_KEY}
LLM_MODEL=${LLM_MODEL:-llama-3.3-70b-versatile}
WHISPER_MODEL=${WHISPER_MODEL}
PIPELINES_API_KEY=0p3n-w3bu!
SITE_ADDRESS=${SITE_ADDRESS}
EOF

echo "[6/6] Building & starting the stack (first build takes ~10 min on 2 vCPU)..."
docker compose -f docker-compose.prod.yml up -d --build

echo ""
echo "======================================================================"
echo " Done. The services warm the whisper model up before serving; give it"
echo " a minute, then:"
echo "   Демо:  https://${SITE_ADDRESS}"
echo "   REST:  https://${SITE_ADDRESS}/health"
echo "          https://${SITE_ADDRESS}/analyze   (POST)"
echo ""
echo " Готовность:  docker compose -f docker-compose.prod.yml logs api | grep preloaded"
echo " Логи:        cd ${APP_DIR} && docker compose -f docker-compose.prod.yml logs -f"
echo "======================================================================"
