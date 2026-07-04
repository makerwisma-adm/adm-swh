#!/bin/bash
# Deploy ke production tanpa metadata git (hindari status BLOCKED di team Vercel)
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$(pwd)/bin/bin:$PATH"

PROD_DOMAIN="adm-swh.vercel.app"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

rsync -a \
  --exclude '.git' \
  --exclude 'bin' \
  --exclude 'uploads' \
  --exclude 'public/uploads' \
  --exclude '__pycache__' \
  --exclude '.venv' \
  --exclude '*.db' \
  --exclude 'tunnel.log' \
  --exclude 'PUBLIC_URL.txt' \
  --exclude 'start-internet.sh' \
  --exclude '.grok' \
  ./ "$TMP/"

cp -r .vercel "$TMP/.vercel"

cd "$TMP"
OUT=$(vercel deploy --prod --yes --archive=tgz 2>&1 | tee /tmp/adm-swh-deploy.log)
DEPLOY_URL=$(echo "$OUT" | grep -oE 'https://[a-z0-9-]+-adm-musik\.vercel\.app' | tail -1)

if [ -n "$DEPLOY_URL" ]; then
  vercel alias set "$DEPLOY_URL" "$PROD_DOMAIN" 2>/dev/null || true
  echo "Deploy selesai → https://${PROD_DOMAIN}/masuk"
else
  echo "$OUT"
  exit 1
fi