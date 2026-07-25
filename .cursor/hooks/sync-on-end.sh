#!/bin/bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$ROOT"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

if git diff --quiet && git diff --cached --quiet; then
  exit 0
fi

HOST="$(hostname 2>/dev/null || echo unknown)"
TIMESTAMP="$(date '+%Y-%m-%d %H:%M' 2>/dev/null || date)"

git add -A
git commit -m "sync: auto-save from ${HOST} at ${TIMESTAMP}" || exit 0
git push 2>/dev/null || true
exit 0
