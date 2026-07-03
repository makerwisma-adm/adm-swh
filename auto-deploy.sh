#!/bin/bash
# Deploy otomatis ke Vercel production saat file berubah (tanpa Git).
# Jalankan di terminal terpisah: ./auto-deploy.sh
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$(pwd)/bin/bin:$PATH"

PROD_URL="https://adm-swh.vercel.app"
INTERVAL="${AUTO_DEPLOY_INTERVAL:-8}"
LOCK="/tmp/adm-swh-deploy.lock"

if ! command -v vercel >/dev/null 2>&1; then
  echo "Vercel CLI belum ada. Install: npm install -g vercel"
  exit 1
fi

if ! vercel whoami >/dev/null 2>&1; then
  echo "Belum login Vercel. Jalankan: vercel login"
  exit 1
fi

echo "Auto-deploy aktif → $PROD_URL"
echo "Cek perubahan setiap ${INTERVAL}s (Ctrl+C untuk berhenti)"
echo ""

last_hash=""
while true; do
  hash=$(find . -type f \
    ! -path './.git/*' \
    ! -path './bin/*' \
    ! -path './.vercel/*' \
    ! -path './uploads/*' \
    ! -path './public/uploads/*' \
    ! -path './__pycache__/*' \
    ! -path './.venv/*' \
    ! -name '*.db' \
    ! -name 'tunnel.log' \
    -print0 2>/dev/null | sort -z | xargs -0 shasum -a 256 2>/dev/null | shasum -a 256 | cut -d' ' -f1)

  if [ "$hash" != "$last_hash" ] && [ -n "$last_hash" ]; then
    if mkdir "$LOCK" 2>/dev/null; then
      trap 'rmdir "$LOCK" 2>/dev/null' EXIT
      echo "[$(date '+%H:%M:%S')] Perubahan terdeteksi, deploy ke production..."
      if vercel deploy --prod --yes; then
        echo "[$(date '+%H:%M:%S')] Selesai → $PROD_URL/login"
      else
        echo "[$(date '+%H:%M:%S')] Deploy gagal, coba lagi saat file berubah."
      fi
      rmdir "$LOCK" 2>/dev/null || true
      trap - EXIT
    fi
  fi
  last_hash="$hash"
  sleep "$INTERVAL"
done