#!/bin/bash
# Jalankan server lokal saja
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8001}"
HOST="${HOST:-0.0.0.0}"

LOCAL_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"

echo "============================================"
echo "  SPPG Keuangan — local dev"
echo "  Lokal  → http://localhost:${PORT}/masuk"
if [ -n "$LOCAL_IP" ]; then
  echo "  HP/LAN → http://${LOCAL_IP}:${PORT}/masuk"
else
  echo "  HP/LAN → http://<IP-komputer-Anda>:${PORT}/masuk"
fi
echo "  Login  → admin / admin123"
echo "============================================"
echo ""

# Pastikan dependency minimal terpasang
if ! python3 -c "import fastapi, uvicorn, jinja2, passlib, slowapi" 2>/dev/null; then
  echo "Menginstall dependencies..."
  python3 -m pip install -r requirements.txt --user -q
fi

exec python3 -m uvicorn main:app --host "$HOST" --port "$PORT" --reload
