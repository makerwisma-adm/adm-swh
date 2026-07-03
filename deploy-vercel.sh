#!/bin/bash
# Deploy manual ke Vercel production (cadangan jika Git tidak dipakai)
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$(pwd)/bin/bin:$PATH"

PROD_DOMAIN="adm-swh.vercel.app"

if ! command -v vercel >/dev/null 2>&1; then
  echo "Vercel CLI belum ada. Jalankan:"
  echo "  export PATH=\"$(pwd)/bin/bin:\$PATH\" && npm install -g vercel"
  exit 1
fi

if ! vercel whoami >/dev/null 2>&1; then
  echo "=== Login Vercel (buka link di browser jika diminta) ==="
  vercel login
fi

echo "=== Deploy ke production ==="
DEPLOY_URL=$(vercel deploy --prod --yes 2>&1 | tee /dev/stderr | grep -oE 'https://[a-z0-9-]+-adm-musik\.vercel\.app' | tail -1)

if [ -n "$DEPLOY_URL" ]; then
  echo ""
  echo "=== Pastikan alias production ==="
  vercel alias set "$DEPLOY_URL" "$PROD_DOMAIN" || true
fi

echo ""
echo "Selesai! URL: https://${PROD_DOMAIN}/login"
echo ""
echo "Untuk deploy otomatis:"
echo "  ./push-and-deploy.sh          # push Git → Vercel auto-deploy"
echo "  ./auto-deploy.sh              # watch file lokal → deploy"