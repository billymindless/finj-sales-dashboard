#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> 프로젝트 경로: $ROOT"

command -v git >/dev/null || { echo "[FAIL] Git이 없습니다."; exit 1; }
echo "[OK] $(git --version)"

if [[ -z "$(git config user.name)" || -z "$(git config user.email)" ]]; then
  echo "[WARN] git user.name / user.email 설정이 필요합니다."
fi

echo "[OK] origin = $(git remote get-url origin)"
echo "==> git pull"
git pull --rebase --autostash 2>/dev/null || git pull

chmod +x .cursor/hooks/sync-on-start.sh .cursor/hooks/sync-on-end.sh

if [[ -f .cursor/hooks.json ]] && grep -q "sync-on-start.sh" .cursor/hooks.json; then
  echo "[OK] Mac용 bash Hook 설정 확인"
else
  echo "[WARN] hooks.json이 Mac용(bash) 설정이 아닙니다."
fi

git push --dry-run >/dev/null 2>&1 && echo "[OK] push 인증 정상" || echo "[WARN] push 인증 확인 필요"

echo
echo "Mac 설정 완료. Cursor Settings -> Hooks 에서 로드 여부를 확인하세요."
