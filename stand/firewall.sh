#!/usr/bin/env bash
# Ограничивает доступ к опубликованным портам контейнеров списком IP: 9443 (стенд) и 8443 (второй экземпляр,
# например установка из docker-compose.yml). Другие порты — FM_FW_PORTS="9443 8443 ...".
# Docker обходит ufw, поэтому правило ставится в цепочку DOCKER-USER.
# Использование: stand/firewall.sh 203.0.113.10 [ещё_IP ...]
set -euo pipefail
[ $# -ge 1 ] || { echo "usage: $0 IP [IP...]"; exit 1; }
iptables -N DOCKER-USER 2>/dev/null || true
iptables -F DOCKER-USER
iptables -A DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
iptables -A DOCKER-USER -i lo -j RETURN
for port in ${FM_FW_PORTS:-9443 8443}; do
  for ip in "$@"; do
    iptables -A DOCKER-USER -i eth0 -p tcp -m conntrack --ctorigdstport "$port" -s "$ip" -j RETURN
  done
  iptables -A DOCKER-USER -i eth0 -p tcp -m conntrack --ctorigdstport "$port" -j DROP
done
iptables -A DOCKER-USER -j RETURN
printf '%s\n' "$@" > "$(dirname "$0")/allowed_ips"
iptables -S DOCKER-USER
