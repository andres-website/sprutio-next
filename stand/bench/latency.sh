#!/usr/bin/env bash
# Задержка сети на тестовом SSH-сервере (в одну сторону): stand/bench/latency.sh 20ms | off
set -euo pipefail
C=sprutio-sshd-1
docker exec "$C" sh -c 'command -v tc >/dev/null || apk add -q iproute2 >/dev/null'
docker exec "$C" tc qdisc del dev eth0 root 2>/dev/null || true
if [ "${1:-off}" != "off" ]; then
  docker exec "$C" tc qdisc add dev eth0 root netem delay "$1"
fi
docker exec "$C" tc qdisc show dev eth0
