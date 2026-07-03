#!/bin/bash
# Deploy SPPG Keuangan ke Vercel (URL permanen *.vercel.app)
set -e
cd "$(dirname "$0")"

export PATH="$(pwd)/bin/bin:$PATH"

if ! command -v vercel >/dev/null 2>&1; then
  echo "Vercel CLI belum ada. Jalankan dulu:"
  echo "  export PATH=\"$(pwd)/bin/bin:\$PATH\" && npm install -g vercel"
  exit 1
fi

echo "=== 1. Login Vercel (buka link di browser jika diminta) ==="
vercel login

echo ""
echo "=== 2. Deploy ke production ==="
DEPLOY_URL=$(vercel deploy --prod --yes 2>&1 | tee /dev/stderr | grep -oE 'https://[a-z0-9-]+-adm-musik\.vercel\.app' | tail -1)
if [ -n "$DEPLOY_URL" ]; then
  echo ""
  echo "=== 2b. Alias ke URL utama ==="
  vercel alias set "$DEPLOY_URL" adm-swh.vercel.app
fi

echo ""
echo "=== 3. Set environment variables di Vercel Dashboard ==="
echo "Buka: https://vercel.com/dashboard → Project → Settings → Environment Variables"
echo ""
echo "Wajib:"
echo "  SECRET_KEY          = (string acak panjang, untuk session)"
echo "  PUBLIC_APP_URL      = https://adm-swh.vercel.app"
echo ""
echo "Untuk database permanen (disarankan):"
echo "  1. Buat database gratis di https://turso.tech"
echo "  2. Tambahkan env vars:"
echo "     TURSO_DATABASE_URL = libsql://....turso.io"
echo "     TURSO_AUTH_TOKEN   = token dari Turso"
echo "  3. Migrasi data lokal:"
echo "     TURSO_DATABASE_URL=... TURSO_AUTH_TOKEN=... python3 scripts/migrate_to_turso.py"
echo "  4. Redeploy: vercel deploy --prod --yes"
echo ""
echo "Selesai! URL permanen: https://adm-swh.vercel.app/login"