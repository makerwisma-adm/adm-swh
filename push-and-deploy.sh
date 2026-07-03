#!/bin/bash
# Simpan perubahan + deploy otomatis ke https://adm-swh.vercel.app
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$(pwd)/bin/bin:$PATH"

MSG="${1:-Update $(date '+%Y-%m-%d %H:%M')}"
PROD_URL="https://adm-swh.vercel.app"

if [ ! -d .git ]; then
  echo "Git belum diinisialisasi."
  exit 1
fi

if ! vercel whoami >/dev/null 2>&1; then
  echo "Login Vercel dulu: vercel login"
  exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin "https://github.com/lauryanhbs-Emen/adm-swh.git"
fi

changed=0
if ! git diff --quiet || ! git diff --cached --quiet; then
  git add -A
  git commit -m "$MSG"
  changed=1
  git push -u origin main 2>/dev/null || echo "(GitHub push opsional — lanjut deploy Vercel)"
fi

if [ "$changed" -eq 0 ]; then
  echo "Tidak ada perubahan file."
  exit 0
fi

echo ""
echo "=== Deploy ke production ==="
vercel deploy --prod --yes
echo ""
echo "Selesai → ${PROD_URL}/login"