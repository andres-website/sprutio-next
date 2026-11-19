"""Экспериментальный быстрый поиск (params.fast): результаты должны совпадать с оригинальным поиском.

Домашний сервер — ripgrep/find в контейнере rpc; SFTP — одна команда rg/grep/find на сервере по SSH.
"""
import uuid

import pytest

# новая возможность форка: на оригинале (FM_STACK=orig) параметр fast игнорируется — модуль пропускается
pytestmark = pytest.mark.fork_only("экспериментальный быстрый поиск")

from fmclient import FMClient
from test_remote import RemoteClient, create_conn, remove_conn

FILES = {
    "a/one.php": "<?php\n$x = 'Needle_Token_99';\n",
    "a/two.js": "var y = 'needle_token_99';\n",           # другой регистр — поиск без учёта регистра
    "a/b/three.txt": "Ёжик в тумане: NEEDLE_TOKEN_99\n",   # кириллица в той же строке
    "a/b/four.css": "body { color: red; }\n",
    "a/.hidden/five.inc": "Needle_Token_99 hidden\n",     # скрытые папки не исключаются
    "a/ignored/six.txt": "Needle_Token_99 ignored\n",     # .gitignore не исключает
    "a/.gitignore": "ignored/\n",
    "c/needle-name.php": "nothing\n",
    "c/Needle-Name.TXT": "nothing\n",                     # имя: с учётом регистра
    "c/big-needle.log": "x" * 5000,
}
BINARY = ("a/bin.dat", b"\x00\x01Needle_Token_99\x00\xff" * 50)  # двоичный — содержимое не ищется


def names(status):
    return sorted(i["path"].rstrip("/") + "/" + i["name"] for i in status["data"])


def tree(client, base):
    for d in sorted({p.rsplit("/", 1)[0] for p in list(FILES) + [BINARY[0]]}):
        parts = d.split("/")
        for i in range(1, len(parts) + 1):
            sub = base + "/" + "/".join(parts[:i])
            try:
                client.mkdir(sub)
            except Exception:
                pass
    for p, content in FILES.items():
        if hasattr(client, "touch"):
            client.touch(base + "/" + p, content)
        else:
            client.newfile(base + "/" + p)
            client.write(base + "/" + p, content)
    d, n = (base + "/" + BINARY[0]).rsplit("/", 1)
    client.upload(d, n, BINARY[1])


@pytest.fixture(scope="module", params=["home", "sftp"])
def target(request, fm):
    if request.param == "home":
        client, conn = fm, None
    else:
        conn = create_conn(fm, "sftp")
        client = RemoteClient(fm, "sftp", int(conn["id"]))
        client.init_session()
    base = "%s/fs-%s" % (client.home.rstrip("/"), uuid.uuid4().hex[:6])
    client.mkdir(base)
    tree(client, base)
    yield client, base
    try:
        client.remove([base])
    finally:
        if conn:
            remove_conn(fm, "sftp", conn["id"])


def search(client, base, url, params, fast):
    p = dict(params, path=base)
    if fast:
        p["fast"] = True
    return names(client.op(url, {"params": p, "session": client.session(base)}))


TEXT_CASES = ["Needle_Token_99", "needle_token_99", "NEEDLE*99", "Needle_Token_9?", "Ёжик", "no-such-text-zzz"]


@pytest.mark.parametrize("text", TEXT_CASES)
def test_text_fast_equals_original(target, text):
    client, base = target
    orig = search(client, base, "/actions/find/text", {"text": text}, False)
    fast = search(client, base, "/actions/find/text", {"text": text}, True)
    assert fast == orig


def test_text_semantics(target):
    client, base = target
    found = search(client, base, "/actions/find/text", {"text": "needle_token_99"}, True)
    short = sorted(f.split(base + "/", 1)[1] for f in found)
    assert short == ["a/.hidden/five.inc", "a/b/three.txt", "a/ignored/six.txt", "a/one.php", "a/two.js"]


NAME_CASES = [
    {"filename": "needle*"},
    {"filename": "*needle*"},
    {"filename": "Needle*"},
    {"filename": "*.php"},
    {"filename": "b", "type_file": False},
    {"filename": "*", "type_dir": False, "file_size": 1000, "size_direction": "more"},
    {"filename": "*.txt", "type_dir": False, "file_size": 30, "size_direction": "less"},
]


@pytest.mark.parametrize("case", NAME_CASES, ids=lambda c: "-".join("%s=%s" % kv for kv in sorted(c.items())))
def test_names_fast_equals_original(target, case):
    client, base = target
    if target[0].__class__.__name__ == "RemoteClient" and case.get("file_size"):
        pytest.skip("фильтр размера по SFTP есть только в быстром поиске")
    params = dict({"file_size": 0, "type_dir": True, "type_file": True, "size_direction": "more"}, **case)
    orig = search(client, base, "/actions/find/files", params, False)
    fast = search(client, base, "/actions/find/files", params, True)
    assert fast == orig


def test_sftp_size_filter_fast_works(fm):
    """Фильтр размера по SFTP в быстром поиске."""
    conn = create_conn(fm, "sftp")
    try:
        client = RemoteClient(fm, "sftp", int(conn["id"]))
        client.init_session()
        base = "%s/fz-%s" % (client.home.rstrip("/"), uuid.uuid4().hex[:6])
        client.mkdir(base)
        client.touch(base + "/small.txt", "x")
        client.touch(base + "/large.txt", "x" * 4000)
        params = {"path": base, "filename": "*.txt", "file_size": 1000, "size_direction": "more",
                  "type_dir": True, "type_file": True, "fast": True}
        found = names(client.op("/actions/find/files", {"params": params, "session": client.session(base)}))
        assert [f.rsplit("/", 1)[1] for f in found] == ["large.txt"]
        client.remove([base])
    finally:
        remove_conn(fm, "sftp", conn["id"])


# --- SFTP: все три движка на удалённом сервере ---------------------------------------------------------
import os as _os
import subprocess as _sp

_RPC_LOG = _os.path.join(_os.path.dirname(__file__), "..", "..", "stand", "logs", "rpc.log")
_PKGS = {"busybox": [], "grep": ["grep"], "rg": ["ripgrep"]}


def _sshd(cmd):
    return _sp.run(["docker", "exec", "sprutio-sshd-1", "sh", "-c", cmd], capture_output=True, text=True,
                   timeout=180)


@pytest.fixture(params=["busybox", "grep", "rg"])
def remote_engine(request):
    _sshd("apk del -q grep ripgrep >/dev/null 2>&1; true")
    if _PKGS[request.param]:
        r = _sshd("apk add -q %s" % " ".join(_PKGS[request.param]))
        if r.returncode:
            pytest.skip("не удалось установить %s на тестовый sshd: %s" % (request.param, r.stderr[:200]))
    yield request.param
    _sshd("apk del -q grep ripgrep >/dev/null 2>&1; true")


def _last_engine():
    with open(_RPC_LOG, errors="replace") as f:
        f.seek(max(0, _os.path.getsize(_RPC_LOG) - 200000))
        lines = [l for l in f.read().splitlines() if "fast find text (ssh):" in l]
    return lines[-1].split("fast find text (ssh):", 1)[1].split(",")[0].strip() if lines else None


@pytest.mark.parametrize("text", ["needle_token_99", "NEEDLE*99", "Ёжик"])
def test_sftp_engines_equal_original(fm, remote_engine, text):
    conn = create_conn(fm, "sftp")
    try:
        client = RemoteClient(fm, "sftp", int(conn["id"]))
        client.init_session()
        base = "%s/fe-%s" % (client.home.rstrip("/"), uuid.uuid4().hex[:6])
        client.mkdir(base)
        tree(client, base)
        orig = search(client, base, "/actions/find/text", {"text": text}, False)
        fast = search(client, base, "/actions/find/text", {"text": text}, True)
        assert _last_engine() == {"busybox": "busybox-grep", "grep": "grep", "rg": "rg"}[remote_engine]
        assert fast == orig
        client.remove([base])
    finally:
        remove_conn(fm, "sftp", conn["id"])
