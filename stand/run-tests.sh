#!/usr/bin/env bash
# Прогон тестов против поднятого стенда.
#   stand/run-tests.sh          — API + E2E
#   stand/run-tests.sh api      — только API
#   stand/run-tests.sh e2e      — только E2E (Playwright, headless Chromium)
# Остальные аргументы передаются pytest.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -x venv/bin/pytest ] || { python3 -m venv venv && venv/bin/pip install -q pytest requests pytest-playwright \
  && venv/bin/playwright install --with-deps chromium; }
case "${1:-all}" in
  api) shift; set -- tests/api "$@";;
  e2e) shift; set -- tests/e2e "$@";;
  all) [ $# -gt 0 ] && shift; set -- tests/api tests/e2e "$@";;
  *) set -- tests/api tests/e2e "$@";;
esac
exec venv/bin/pytest -q -p no:cacheprovider -W ignore "$@"
