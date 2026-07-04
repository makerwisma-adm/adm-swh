#!/bin/bash
# Jalankan server lokal (8001) + auto-deploy ke Vercel production
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$(pwd)/bin/bin:$PATH"

PROD_URL="https://adm-swh.vercel.app"

if ! vercel whoami >/dev/null 2>&1; then
  echo "Login Vercel dulu: vercel login"
  exit 1
fi

cleanup() {
  echo ""
  echo "Menghentikan server dan auto-deploy..."
  kill "$DEPLOY_PID" 2>/dev/null || true
  kill "$SERVER_PID" 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

echo "============================================"
echo "  Dev lokal  → http://localhost:8001/masuk"
echo "  Production → ${PROD_URL}/masuk"
echo "  Auto-deploy aktif (perubahan file → Vercel)"
echo "============================================"
echo ""

./auto-deploy.sh &
DEPLOY_PID=$!

python3 -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload &
SERVER_PID=$!

wait "$SERVER_PID"