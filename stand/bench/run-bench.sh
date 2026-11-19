#!/usr/bin/env bash
# Замеры поиска на тестовом проекте (~10k файлов): SFTP с задержкой сети и домашний сервер.
# Итог — stand/logs/bench.log. Оригинальный SFTP-поиск по содержимому с задержкой идёт ~16 мин,
# поэтому он здесь не повторяется (см. bench-orig-lat.log).
set -uo pipefail
cd "$(dirname "$0")/../.."
LOG=stand/logs/bench.log
B="venv/bin/python -u -W ignore tests/bench/bench_search.py"
sshd() { docker exec sprutio-sshd-1 sh -c "$1"; }
{
  echo "=== $(date -Is) SFTP, задержка 20ms в одну сторону (пинг ~40 мс)"
  stand/bench/latency.sh 20ms >/dev/null
  sshd 'apk del -q grep ripgrep >/dev/null 2>&1; apk add -q grep'
  echo "--- на сервере GNU grep"; $B sftp ./project fast
  sshd 'apk add -q ripgrep'
  echo "--- на сервере ripgrep"; $B sftp ./project fast
  sshd 'apk del -q grep ripgrep >/dev/null 2>&1; true'
  echo "--- на сервере BusyBox grep"; $B sftp ./project fast
  stand/bench/latency.sh off >/dev/null

  echo "=== $(date -Is) домашний сервер (локальный диск)"
  H=stand/sandbox-root/home/fmtest/project
  [ -d "$H" ] || { cp -a /tmp/bench-src/project "$H" && chown -R 1000:1000 "$H"; }
  $B home /home/fmtest/project
  $B home /home/fmtest/project fast
  echo "=== $(date -Is) done"
} > "$LOG" 2>&1
