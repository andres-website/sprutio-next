"""Хранение паролей в форке: сессия, сохранённые подключения, логи.

Тесты смотрят «внутрь» стенда: redis (docker exec), rpc.db и логи на хосте (stand/var, stand/logs).
"""
import base64
import json
import os
import sqlite3
import subprocess
import time

import pytest

from conftest import _env
from fmclient import FMClient
from test_remote import RemoteClient, conn_params, create_conn, remove_conn

STAND = os.path.join(os.path.dirname(__file__), "..", "..", "stand")
OLD_COOKIE_SECRET = "943a702d06f34599aee1f8da8ef9f7296031d699"  # был зашит в app/config/settings.py


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout


def redis_values(pattern):
    keys = sh("docker", "exec", "sprutio-redis-1", "redis-cli", "--scan", "--pattern", pattern).split()
    return [sh("docker", "exec", "sprutio-redis-1", "redis-cli", "get", k) for k in keys]


def login(creds):
    c = FMClient()
    r = c.s.post(c.base + "/auth", data={"login": creds[0], "password": creds[1], "language": "en"},
                 allow_redirects=False, timeout=30)
    assert r.json()["error"] is False
    c.init_session()
    return c, r


@pytest.mark.orig_differs()
def test_session_password_not_in_redis(creds):
    login(creds)
    values = redis_values("FM::session::%s::*" % creds[0])
    assert values, "нет сессий в redis"
    assert not any(creds[1] in v for v in values)


@pytest.mark.orig_differs()
def test_session_cookie_flags(creds):
    _, r = login(creds)
    cookie = [h for h in r.raw.headers.getlist("Set-Cookie") if h.startswith("token=")][0].lower()
    assert "httponly" in cookie and "secure" in cookie


@pytest.mark.orig_differs()
def test_cookie_signed_with_old_secret_rejected(creds):
    import tornado.web
    c, _ = login(creds)
    signed = c.s.cookies.get("token")
    # значение подписанной cookie tornado v2: 2|1:0|10:<ts>|5:token|<len>:<base64 value>|<sig>
    value = base64.b64decode(signed.split("|")[4].split(":", 1)[1]).decode()
    forged = tornado.web.create_signed_value(OLD_COOKIE_SECRET, "token", value).decode()
    f = FMClient()
    f.s.cookies.set("token", forged)
    r = f.post("/actions/files/list", {"path": c.home, "session": c.session(c.home)})
    assert r.status_code in (302, 403)


def test_logout_invalidates_old_cookie(creds):
    """Регрессия порта: в redis-py 3+ exists() возвращает число, обёртка RedisConnector.delete() сравнивала
    "is True" и ничего не удаляла — после выхода старая cookie оставалась рабочей."""
    c, _ = login(creds)
    old = c.s.cookies.get("token")
    c.post("/actions/main/logout")
    f = FMClient()
    f.s.cookies.set("token", old)
    r = f.post("/actions/files/list", {"path": c.home, "session": c.session(c.home)})
    assert r.status_code in (302, 403)


@pytest.mark.orig_differs()
@pytest.mark.parametrize("kind", ["sftp", "ftp", "webdav"])
def test_connection_password_not_returned(fm, kind):
    secret = conn_params(kind)["password"]
    d = create_conn(fm, kind)
    try:
        assert secret not in json.dumps(d)
        listing = fm.call("/actions/home/init_callback")
        assert secret not in json.dumps(listing)
    finally:
        remove_conn(fm, kind, d["id"])


@pytest.mark.orig_differs()
def test_connection_passwords_encrypted_at_rest(fm):
    ids = {k: create_conn(fm, k)["id"] for k in ("sftp", "ftp", "webdav")}
    try:
        db = sqlite3.connect(os.path.join(STAND, "var", "rpc.db"))
        rows = []
        for table in ("ftp_servers", "sftp_servers", "webdav_servers"):
            rows += [r[0] for r in db.execute("SELECT password FROM %s" % table)]
        db.close()
        e = _env()
        for secret in (e["FM_SFTP_PASS"], e["FM_FTP_PASS"], e["FM_DAV_PASS"]):
            assert not any(secret in (p or "") for p in rows)
        assert rows and all((p or "").startswith("fm1:") for p in rows if p)
    finally:
        for k, i in ids.items():
            remove_conn(fm, k, i)


@pytest.mark.parametrize("kind", [
    pytest.param("sftp", marks=pytest.mark.orig_differs()),
    pytest.param("ftp", marks=pytest.mark.orig_differs()),
    # на оригинале результат WebDAV может отличаться
    pytest.param("webdav", marks=pytest.mark.orig_differs(strict=False))])
def test_update_with_empty_password_keeps_it(fm, kind):
    d = create_conn(fm, kind)
    try:
        params = dict(conn_params(kind), id=d["id"], password="")
        fm.call("/actions/%s/update" % kind, {"params": params})
        RemoteClient(fm, kind, int(d["id"])).init_session()  # подключение по-прежнему работает
    finally:
        remove_conn(fm, kind, d["id"])


@pytest.mark.orig_differs()
def test_passwords_not_in_logs(creds):
    rpc_log = os.path.join(STAND, "logs", "rpc.log")
    offset = os.path.getsize(rpc_log) if os.path.exists(rpc_log) else 0
    since = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - 2))
    c, _ = login(creds)
    c.ls(c.home)
    for kind in ("sftp", "ftp", "webdav"):
        d = create_conn(c, kind)
        try:
            r = RemoteClient(c, kind, int(d["id"]))
            r.init_session()
            r.ls(r.home)
            c.call("/actions/%s/update" % kind, {"params": dict(conn_params(kind), id=d["id"])})
        finally:
            remove_conn(c, kind, d["id"])
    time.sleep(1)
    with open(rpc_log, errors="replace") as f:
        f.seek(offset)
        rpc_text = f.read()
    app_text = subprocess.run(["docker", "logs", "--since", since, "sprutio-app-1"],
                              capture_output=True, text=True, timeout=60)
    app_text = app_text.stdout + app_text.stderr
    e = _env()
    secrets = [creds[1], e["FM_SFTP_PASS"], e["FM_FTP_PASS"], e["FM_DAV_PASS"]]
    assert rpc_text and app_text
    leaks = [s[:4] + "…" for s in secrets if s in rpc_text or s in app_text]
    assert leaks == [], "пароли найдены в логах: %s" % leaks
