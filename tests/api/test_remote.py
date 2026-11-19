"""Удалённые серверы (как в xftp): SFTP, FTP, WebDAV — тестовые серверы из стенда, внутри сети Docker.

  sftp   sshd:2222       (linuxserver/openssh-server)   сессия path='.' (домашний каталог)
  ftp    ftpd:21         (pyftpdlib, passive)           сессия path='/'
  webdav http://webdav/  (Apache mod_dav, Basic)        сессия path='/'
Подключение: /actions/<type>/create {params:{host,port?,user,password}} → id;
сессия панели {"type": <type>, "server_id": id, "path": ...}.
"""
import os
import uuid

import pytest

from conftest import _env
from fmclient import FMClient, FMError

CYR = "Удалённый файл: <p>ёж</p>\n"


def conn_params(kind, password=None):
    e = _env()
    if kind == "sftp":
        return {"host": "sshd", "port": 2222, "user": e["FM_SFTP_USER"], "password": password or e["FM_SFTP_PASS"]}
    if kind == "ftp":
        return {"host": "ftpd", "port": 21, "user": e["FM_FTP_USER"], "password": password or e["FM_FTP_PASS"]}
    return {"host": "http://webdav/", "user": e["FM_DAV_USER"], "password": password or e["FM_DAV_PASS"]}


START_PATH = {"sftp": ".", "ftp": "/", "webdav": "/"}
# операции, которых у протокола нет в rpc (workers/<type>/)
UNSUPPORTED = {
    "ftp": {"find"},
    "webdav": {"find", "newfile"},
}


class RemoteClient(FMClient):
    """Операции FMClient, но сессия панели — удалённое подключение."""

    def __init__(self, base_client, kind, server_id):
        super().__init__(base_client.base)
        self.s = base_client.s
        self.kind = kind
        self.server_id = server_id

    def session(self, path=None):
        return {"type": self.kind, "server_id": self.server_id, "path": path or self.home}

    def init_session(self, path=None):
        d = self.call("/actions/main/init_session", {"session": self.session(path or START_PATH[self.kind])})["data"]
        self.home = d["session"]["path"]
        return d

    def touch(self, path, content=""):
        """Создать файл: newfile там, где он есть; на WebDAV — сразу write."""
        if "newfile" not in UNSUPPORTED.get(self.kind, ()):
            self.newfile(path)
            if content:
                self.write(path, content)
        else:
            self.write(path, content)


def need(remote, op):
    if op in UNSUPPORTED.get(remote.kind, ()):
        pytest.skip("%s: операции %s нет в оригинальном rpc" % (remote.kind, op))


def create_conn(fm, kind, password=None):
    return fm.call("/actions/%s/create" % kind, {"params": conn_params(kind, password)})["data"]


def remove_conn(fm, kind, conn_id):
    fm.call("/actions/%s/remove" % kind, {"params": {"id": conn_id}})


_WEBDAV_ORIG = pytest.mark.orig_differs(strict=False)


@pytest.fixture(scope="module", params=["sftp", "ftp", pytest.param("webdav", marks=_WEBDAV_ORIG)])
def remote(request, fm):
    kind = request.param
    d = create_conn(fm, kind)
    c = RemoteClient(fm, kind, int(d["id"]))
    c.init_session()
    yield c
    try:
        remove_conn(fm, kind, d["id"])
    except Exception:
        pass


@pytest.fixture()
def rwork(remote):
    base = remote.home.rstrip("/")
    path = "%s/t-%s" % (base, uuid.uuid4().hex[:8])
    remote.mkdir(path)
    yield path
    try:
        remote.remove([path])
    except Exception:
        pass


# ---------------------------------------------------------------------------

def test_connection_listed(fm, remote):
    d = fm.call("/actions/home/init_callback")["data"]
    conns = d["webdav_connections"] if remote.kind == "webdav" else d["connections"]
    assert any(int(c["id"]) == remote.server_id for c in conns)


def test_start_listing(remote):
    assert remote.home == START_PATH[remote.kind]
    assert isinstance(remote.ls(remote.home), dict)


def test_mkdir_write_read(remote, rwork):
    remote.mkdir(rwork + "/sub")
    remote.touch(rwork + "/index.html", CYR)
    assert remote.read(rwork + "/index.html")["content"] == CYR
    items = remote.ls(rwork)
    assert items["sub"]["is_dir"] == 1 and items["index.html"]["is_dir"] == 0


def test_rename_and_remove(remote, rwork):
    remote.touch(rwork + "/a.txt", "x")
    remote.rename(rwork + "/a.txt", rwork + "/b.txt")
    assert set(remote.ls(rwork)) == {"b.txt"}
    remote.remove([rwork + "/b.txt"])
    assert remote.ls(rwork) == {}


def test_copy_inside(remote, rwork):
    remote.mkdir(rwork + "/src")
    remote.mkdir(rwork + "/dst")
    remote.touch(rwork + "/src/f.txt", "inside")
    remote.copy([rwork + "/src/f.txt"], rwork + "/dst")
    assert remote.read(rwork + "/dst/f.txt")["content"] == "inside"


def test_copy_home_to_remote(fm, remote, work, rwork):
    fm.newfile(work + "/up.txt")
    fm.write(work + "/up.txt", CYR)
    fm.op("/actions/files/copy", {"paths": [work + "/up.txt"], "target": remote.session(rwork),
                                  "overwrite": False, "session": fm.session(work)})
    assert remote.read(rwork + "/up.txt")["content"] == CYR


def test_copy_remote_to_home(fm, remote, work, rwork):
    remote.touch(rwork + "/down.txt", CYR)
    remote.op("/actions/files/copy", {"paths": [rwork + "/down.txt"], "target": fm.session(work),
                                      "overwrite": False, "session": remote.session(rwork)})
    assert fm.read(work + "/down.txt")["content"] == CYR


def test_copy_directory_home_to_remote(fm, remote, work, rwork):
    fm.mkdir(work + "/tree")
    fm.mkdir(work + "/tree/inner")
    fm.newfile(work + "/tree/inner/x.css")
    fm.write(work + "/tree/inner/x.css", "a{}")
    fm.op("/actions/files/copy", {"paths": [work + "/tree"], "target": remote.session(rwork),
                                  "overwrite": False, "session": fm.session(work)})
    assert remote.read(rwork + "/tree/inner/x.css")["content"] == "a{}"


def test_move_remote_to_home(fm, remote, work, rwork):
    remote.touch(rwork + "/mv.txt", "moved")
    remote.op("/actions/files/move", {"paths": [rwork + "/mv.txt"], "target": fm.session(work),
                                      "overwrite": False, "session": remote.session(rwork)})
    assert fm.read(work + "/mv.txt")["content"] == "moved"
    assert "mv.txt" not in remote.ls(rwork)


def test_upload_to_remote(remote, rwork):
    payload = os.urandom(300 * 1024 + 5)
    remote.upload(rwork, "up.bin", payload)
    assert remote.ls(rwork)["up.bin"]["size"] == len(payload)


def test_download_from_remote(remote, rwork):
    remote.touch(rwork + "/dl.txt", "from remote")
    r = remote.download([rwork + "/dl.txt"])
    assert r.status_code == 200 and r.content == b"from remote"


def test_find_files(remote, rwork):
    need(remote, "find")
    remote.touch(rwork + "/needle-remote.txt", "x")
    st = remote.find_files(rwork, "needle*")
    assert "needle-remote.txt" in repr(st)


@pytest.mark.parametrize("kind", ["sftp", "ftp", pytest.param("webdav", marks=_WEBDAV_ORIG)])
def test_wrong_password(fm, kind):
    d = create_conn(fm, kind, password="wrong-password")
    c = RemoteClient(fm, kind, int(d["id"]))
    try:
        with pytest.raises(FMError):
            c.init_session()
    finally:
        remove_conn(fm, kind, d["id"])
