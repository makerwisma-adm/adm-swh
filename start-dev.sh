#!/bin/bash
# Jalankan server lokal (8001). Auto-deploy Vercel opsional.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$(pwd)/bin/bin:$PATH"

PROD_URL="https://adm-swh.vercel.app"
PORT="${PORT:-8001}"

cleanup() {
  echo ""
  echo "Menghentikan server..."
  [[ -n "${DEPLOY_PID:-}" ]] && kill "$DEPLOY_PID" 2>/dev/null || true
  [[ -n "${SERVER_PID:-}" ]] && kill "$SERVER_PID" 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

USE_DEPLOY=0
if command -v vercel >/dev/null 2>&1 && vercel whoami >/dev/null 2>&1; then
  USE_DEPLOY=1
else
  echo "Catatan: Vercel CLI belum login — hanya server lokal yang dijalankan."
  echo "  (Opsional: vercel login, lalu jalankan ulang untuk auto-deploy)"
  echo ""
fi

echo "============================================"
echo "  Dev lokal  → http://localhost:${PORT}/masuk"
echo "  Login      → admin / admin123"
if [[ "$USE_DEPLOY" -eq 1 ]]; then
  echo "  Production → ${PROD_URL}/masuk"
  echo "  Auto-deploy aktif"
else
  echo "  Auto-deploy nonaktif"
fi
echo "============================================"
echo ""

if [[ "$USE_DEPLOY" -eq 1 ]]; then
  ./auto-deploy.sh &
  DEPLOY_PID=$!
fi

python3 -m uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload &
SERVER_PID=$!

wait "$SERVER_PID"
