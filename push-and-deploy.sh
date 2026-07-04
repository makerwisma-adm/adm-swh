#!/bin/bash
# Simpan perubahan + deploy otomatis ke https://adm-swh.vercel.app
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$(pwd)/bin/bin:$PATH"

MSG="${1:-Update $(date '+%Y-%m-%d %H:%M')}"
PROD_URL="https://adm-swh.vercel.app"

if ! vercel whoami >/dev/null 2>&1; then
  echo "Login Vercel dulu: vercel login"
  exit 1
fi

if [ -d .git ]; then
  if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "https://github.com/lauryanhbs-Emen/adm-swh.git" 2>/dev/null || true
  fi
  if ! git diff --quiet || ! git diff --cached --quiet; then
    git add -A
    git commit -m "$MSG"
    git push -u origin main 2>/dev/null || true
  fi
fi

echo "=== Deploy ke production ==="
./vercel-deploy.sh