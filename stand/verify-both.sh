#!/usr/bin/env bash
# Полная сверка: эталонные тесты на оригинале (FM_STACK=orig) и на форке (собранные образы).
# Итог — в stand/logs/verify.log. В конце стенд остаётся на форке.
set -uo pipefail
cd "$(dirname "$0")"
LOG=logs/verify.log
mkdir -p logs
{
  echo "=== $(date -Is) ORIGINAL"
  ./dev.sh up-orig >/dev/null 2>&1; sleep 20
  FM_STACK=orig ./run-tests.sh 2>&1 | tail -3
  echo "=== $(date -Is) NEXT (images)"
  ./dev.sh up-next >/dev/null 2>&1; sleep 20
  ./run-tests.sh 2>&1 | tail -3
  echo "=== $(date -Is) done"
} > "$LOG" 2>&1
