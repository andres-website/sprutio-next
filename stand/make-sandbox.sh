#!/usr/bin/env bash
# Создаёт песочницу sandbox-root, которую rpc видит как "корень хоста".
# passwd/group/shadow берутся из самого образа rpc (root заблокирован "*"),
# добавляется тестовый пользователь fmtest с паролем из stand/.env.
set -euo pipefail
cd "$(dirname "$0")"

# тестовые учётки стенда (песочница и тестовые SFTP/FTP/WebDAV-серверы) — генерируются, если их ещё нет
touch .env && chmod 600 .env
for pair in FM_TEST_USER=fmtest FM_SFTP_USER=sftpuser FM_FTP_USER=ftpuser FM_DAV_USER=davuser; do
  key=${pair%%=*}
  grep -q "^$key=" .env || echo "$pair" >> .env
  pass=${key%_USER}_PASS
  grep -q "^$pass=" .env || echo "$pass=$(openssl rand -hex 12)" >> .env
done
source .env

SB=sandbox-root
mkdir -p "$SB/etc" ssl logs var downloads

IMG=${SPRUTIO_RPC_IMAGE:-beget/sprutio-rpc}
for f in passwd group shadow; do
  docker run --rm --entrypoint cat "$IMG" /etc/$f > "$SB/etc/$f"
done
# root и системные учётки — без пароля
sed -i -E 's/^([^:]+):[^:]*:/\1:*:/' "$SB/etc/shadow"

HASH=$(openssl passwd -6 "$FM_TEST_PASS")
grep -q "^$FM_TEST_USER:" "$SB/etc/passwd" || {
  echo "$FM_TEST_USER:x:1000:1000:FM test:/home/$FM_TEST_USER:/bin/bash" >> "$SB/etc/passwd"
  echo "$FM_TEST_USER:x:1000:" >> "$SB/etc/group"
  echo "$FM_TEST_USER:$HASH:20000:0:99999:7:::" >> "$SB/etc/shadow"
}
chmod 644 "$SB/etc/passwd" "$SB/etc/group"; chmod 640 "$SB/etc/shadow"

# Тестовые данные (эталонный набор для тестов пересоздаётся тестами в ~/fmtest-work)
H="$SB/home/$FM_TEST_USER"
mkdir -p "$H/site/css" "$H/docs"
[ -f "$H/site/index.html" ] || cat > "$H/site/index.html" <<'EOF'
<!doctype html>
<html><head><meta charset="utf-8"><title>test</title>
<link rel="stylesheet" href="css/style.css"></head>
<body><h1>Привет, sprutio</h1></body></html>
EOF
[ -f "$H/site/css/style.css" ] || printf 'body { font-family: sans-serif; }\n' > "$H/site/css/style.css"
[ -f "$H/docs/readme.txt" ] || printf 'test file\n' > "$H/docs/readme.txt"
chown -R 1000:1000 "$H"; chmod 755 "$SB/home" ; chmod 700 "$H"
echo "sandbox ready: $SB (user $FM_TEST_USER)"
