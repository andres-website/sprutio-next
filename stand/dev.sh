#!/usr/bin/env bash
# Обёртка над docker compose для стенда.
#   stand/dev.sh up            — поднять в dev-режиме (исходники из репозитория)
#   stand/dev.sh up-orig       — поднять оригинал как есть (только образы)
#   stand/dev.sh build-next | up-next — новый стек (Python 3.12), собранный из исходников
#   stand/dev.sh up-next-dev   — новый стек + исходники из репозитория (правка → restart app|rpc)
#   stand/dev.sh restart app   — перезапустить сервис после правки Python
#   stand/dev.sh up-ai [модель] — Ollama для ИИ-подсказок (127.0.0.1:11434) + скачать модель
#   stand/dev.sh logs rpc      — логи
#   stand/dev.sh <любая команда compose>
set -euo pipefail
cd "$(dirname "$0")"
[ -s allowed_ips ] && ./firewall.sh $(cat allowed_ips) >/dev/null
DEV=(-f compose.yml -f compose.dev.yml)
case "${1:-}" in
  up) shift; exec docker compose "${DEV[@]}" up -d --remove-orphans "$@";;
  # -V для frontend: статика лежит в анонимном томе, который compose иначе переносит в новый контейнер —
  # обновлённые файлы фронта не доходили бы до nginx
  up-orig) shift; docker compose -f compose.yml up -d --force-recreate -V frontend \
             && exec docker compose -f compose.yml up -d --force-recreate --remove-orphans "$@";;
  build-next) shift; docker compose -f compose.yml -f compose.next.yml --profile build build base \
                && exec docker compose -f compose.yml -f compose.next.yml build app rpc nginx frontend cron "$@";;
  up-next-dev) shift; exec docker compose -f compose.yml -f compose.next.yml -f compose.dev.yml up -d --force-recreate --remove-orphans "$@";;
  up-next) shift; docker compose -f compose.yml -f compose.next.yml up -d --force-recreate -V frontend \
             && exec docker compose -f compose.yml -f compose.next.yml up -d --force-recreate --remove-orphans "$@";;
  up-ai) shift; docker compose -f compose.yml -f compose.next.yml --profile ai up -d ollama \
           && exec docker compose -f compose.yml -f compose.next.yml exec -T ollama ollama pull "${1:-qwen2.5-coder:0.5b}";;
  logs-next) shift; exec docker compose -f compose.yml -f compose.next.yml logs --tail=100 "$@";;
  logs) shift; exec docker compose "${DEV[@]}" logs --tail=100 "$@";;
  *) exec docker compose "${DEV[@]}" "$@";;
esac
