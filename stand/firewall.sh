#!/usr/bin/env bash
# Ограничивает доступ к опубликованным портам контейнеров (9443) списком IP.
# Docker обходит ufw, поэтому правило ставится в цепочку DOCKER-USER.
# Использование: stand/firewall.sh 203.0.113.10 [ещё_IP ...]
set -euo pipefail
[ $# -ge 1 ] || { echo "usage: $0 IP [IP...]"; exit 1; }
iptables -N DOCKER-USER 2>/dev/null || true
iptables -F DOCKER-USER
iptables -A DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
iptables -A DOCKER-USER -i lo -j RETURN
for ip in "$@"; do
  iptables -A DOCKER-USER -i eth0 -p tcp -m conntrack --ctorigdstport 9443 -s "$ip" -j RETURN
done
iptables -A DOCKER-USER -i eth0 -p tcp -m conntrack --ctorigdstport 9443 -j DROP
iptables -A DOCKER-USER -j RETURN
printf '%s\n' "$@" > "$(dirname "$0")/allowed_ips"
iptables -S DOCKER-USER
