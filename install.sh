#!/usr/bin/env bash
# sprutio-next: установка/обновление на этом сервере.
#   ./install.sh            — собрать образы из исходников и запустить (повторный запуск = обновление)
#   ./install.sh stop       — остановить
#   ./install.sh logs [rpc] — логи
set -euo pipefail
cd "$(dirname "$0")"

die() { echo "Ошибка: $*" >&2; exit 1; }
command -v docker >/dev/null || die "нужен Docker — https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 || die "нужен Docker Compose v2 (команда 'docker compose')"
[ "$(id -u)" = 0 ] || docker info >/dev/null 2>&1 || die "запустите от root или пользователем из группы docker"

case "${1:-install}" in
  stop) exec docker compose down;;
  logs) shift; exec docker compose logs --tail=100 "$@";;
  install) ;;
  *) die "неизвестная команда: $1 (install | stop | logs)";;
esac

mkdir -p data/ssl data/var data/logs data/downloads
# воркеры работают от имени вошедшего пользователя: им нужен доступ к базе настроек (var) и временным файлам
chmod 755 data data/ssl data/var data/logs
chmod 1777 data/downloads

echo "== Сборка образов (в первый раз ~10 минут)"
docker compose --profile build build base
docker compose build app rpc nginx frontend cron

echo "== Запуск"
# -V для frontend: статика фронта лежит в анонимном томе — без пересоздания обновления не доходят до nginx
docker compose up -d --force-recreate -V frontend
docker compose up -d --remove-orphans

# порт может быть задан в .env рядом с docker-compose.yml (его читает и docker compose)
if [ -z "${FM_HTTPS_PORT:-}" ] && [ -f .env ]; then
  FM_HTTPS_PORT=$(sed -n 's/^FM_HTTPS_PORT=//p' .env | tail -1)
fi
PORT=${FM_HTTPS_PORT:-9443}
HOST=$(hostname -I 2>/dev/null | awk '{print $1}')
cat <<EOF

Готово: https://${HOST:-<адрес-сервера>}:${PORT##*:}
Вход — логин и пароль пользователя этого сервера (сертификат самоподписанный — браузер предупредит).
EOF
case "$PORT" in 127.0.0.1:*|localhost:*) echo "Порт доступен только с этого сервера." ;;
  *) echo "Порт открыт всем: при необходимости ограничьте доступ файрволом." ;; esac
