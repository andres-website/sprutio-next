"""Характеризационные тесты HTTP API sprutio.

Фиксируют поведение оригинала (образы beget/sprutio-* 2017 г.) — эталон для порта на новый стек.
Запуск: stand/run-tests.sh  (или venv/bin/pytest tests/api -v)
"""
import io
import tarfile
import zipfile

import pytest

from fmclient import FMClient, FMError

CYR = "Привет, мир! <div class=\"x\">ёж</div>\n"


# --- авторизация ------------------------------------------------------------

def test_login_wrong_password(creds):
    c = FMClient()
    data = c.login(creds[0], "definitely-wrong")
    assert data["error"] is True


def test_login_root_is_locked():
    c = FMClient()
    assert c.login("root", "root")["error"] is True


def test_api_requires_auth():
    c = FMClient()
    r = c.post("/actions/files/list", {"path": "/", "session": c.session("/")})
    assert r.status_code in (302, 403)


def test_login_and_home(fm, creds):
    assert fm.home == "/home/%s" % creds[0]
    items = fm.ls(fm.home)
    assert {"docs", "site"} <= set(items)
    assert items["site"]["is_dir"] == 1


def test_listing_fields(fm):
    item = fm.ls(fm.home + "/docs")["readme.txt"]
    for key in ("name", "ext", "size", "mode", "owner", "mtime", "is_dir", "is_link", "base64"):
        assert key in item, key
    assert item["ext"] == "txt"
    assert item["size"] == len("test file\n")


def test_init_callback(fm, creds):
    d = fm.call("/actions/home/init_callback")["data"]
    assert d["account"]["login"] == creds[0]


# --- файлы ------------------------------------------------------------------

def test_mkdir_and_newfile(fm, work):
    fm.mkdir(work + "/sub")
    fm.newfile(work + "/empty.txt")
    items = fm.ls(work)
    assert items["sub"]["is_dir"] == 1
    assert items["empty.txt"]["size"] == 0


def test_write_read_utf8(fm, work):
    p = work + "/index.html"
    fm.newfile(p)
    fm.write(p, CYR)
    d = fm.read(p)
    assert d["content"] == CYR
    assert d["encoding"].lower().replace("_", "-") in ("utf-8", "utf8")


def test_rename(fm, work):
    fm.newfile(work + "/a.txt")
    fm.rename(work + "/a.txt", work + "/b.txt")
    assert set(fm.ls(work)) == {"b.txt"}


def test_create_copy(fm, work):
    fm.newfile(work + "/a.txt")
    fm.create_copy([work + "/a.txt"])
    names = set(fm.ls(work))
    assert "a.txt" in names and len(names) == 2


def test_copy_and_move(fm, work):
    fm.mkdir(work + "/src")
    fm.mkdir(work + "/dst")
    fm.newfile(work + "/src/f.txt")
    fm.write(work + "/src/f.txt", "data")
    fm.copy([work + "/src/f.txt"], work + "/dst")
    assert "f.txt" in fm.ls(work + "/src") and "f.txt" in fm.ls(work + "/dst")
    fm.mkdir(work + "/dst2")
    fm.move([work + "/src/f.txt"], work + "/dst2")
    assert "f.txt" not in fm.ls(work + "/src")
    assert fm.read(work + "/dst2/f.txt")["content"] == "data"


def test_copy_directory_recursive(fm, work):
    fm.mkdir(work + "/tree")
    fm.mkdir(work + "/tree/inner")
    fm.newfile(work + "/tree/inner/x.css")
    fm.mkdir(work + "/out")
    fm.copy([work + "/tree"], work + "/out")
    assert "x.css" in fm.ls(work + "/out/tree/inner")


def test_remove(fm, work):
    fm.newfile(work + "/a.txt")
    fm.mkdir(work + "/d")
    fm.newfile(work + "/d/b.txt")
    fm.remove([work + "/a.txt", work + "/d"])
    assert fm.ls(work) == {}


def test_chmod(fm, work):
    fm.newfile(work + "/a.sh")
    fm.chmod([work + "/a.sh"], "755")
    assert fm.ls(work)["a.sh"]["mode"] == "755"


def test_analyze_size(fm, work):
    fm.newfile(work + "/a.txt")
    fm.write(work + "/a.txt", "x" * 1000)
    st = fm.analyze_size(work)
    assert st["status"] == "success"


# --- архивы ---------------------------------------------------------------

@pytest.mark.parametrize("typ,ext", [("zip", ".zip"), ("gzip", ".tar.gz"), ("bz2", ".tar.bz2"), ("tar", ".tar")])
def test_archive_roundtrip(fm, work, typ, ext):
    fm.mkdir(work + "/pack")
    fm.newfile(work + "/pack/a.txt")
    fm.write(work + "/pack/a.txt", CYR)
    arc = work + "/arch" + ext
    fm.archive_create(work + "/arch", [work + "/pack"], typ)
    assert ("arch" + ext) in fm.ls(work)
    fm.mkdir(work + "/out")
    fm.archive_extract(arc, work + "/out")
    # содержимое восстановилось
    paths = [work + "/out/pack/a.txt", work + "/out/a.txt"]
    contents = []
    for p in paths:
        try:
            contents.append(fm.read(p)["content"])
        except FMError:
            pass
    assert CYR in contents


# --- поиск ----------------------------------------------------------------

def test_find_files(fm, work):
    fm.mkdir(work + "/x")
    fm.newfile(work + "/x/needle-file.txt")
    st = fm.find_files(work, "needle*")  # fnmatch: нужен шаблон
    assert "needle-file.txt" in repr(st)


def test_find_text(fm, work):
    fm.newfile(work + "/hay.txt")
    fm.write(work + "/hay.txt", "aaa\nUNIQUE_TOKEN_42\nbbb\n")
    st = fm.find_text(work, "UNIQUE_TOKEN_42")
    assert "hay.txt" in repr(st)


# --- загрузка / скачивание --------------------------------------------------

def test_upload(fm, work):
    payload = ("загрузка " * 100).encode()
    fm.upload(work, "up.txt", payload)
    items = fm.ls(work)
    assert items["up.txt"]["size"] == len(payload)


_BIG_UPLOAD_DIFFERS = pytest.mark.orig_differs()


@pytest.mark.parametrize("size", [
    pytest.param(64 * 1024 + 7, marks=pytest.mark.orig_differs(strict=False)),
    pytest.param(5 * 1024 * 1024 + 3, marks=_BIG_UPLOAD_DIFFERS)])
def test_upload_large_roundtrip(fm, work, size):
    import hashlib
    import os as _os
    payload = _os.urandom(size)
    fm.upload(work, "big.bin", payload)
    assert fm.ls(work)["big.bin"]["size"] == size
    r = fm.download([work + "/big.bin"])
    assert r.status_code == 200
    assert hashlib.sha256(r.content).hexdigest() == hashlib.sha256(payload).hexdigest()


def test_download_single(fm, work):
    fm.newfile(work + "/dl.txt")
    fm.write(work + "/dl.txt", "download me")
    r = fm.download([work + "/dl.txt"])
    assert r.status_code == 200
    assert r.content == b"download me"


def test_download_zip(fm, work):
    fm.newfile(work + "/z.txt")
    fm.write(work + "/z.txt", "zipped")
    r = fm.download([work + "/z.txt"], mode="zip")
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert any(n.endswith("z.txt") for n in zf.namelist())


# --- границы прав (песочница) ----------------------------------------------

@pytest.mark.orig_differs()
def test_cannot_read_shadow(fm):
    with pytest.raises(FMError):
        fm.read("/etc/shadow")


def test_cannot_write_outside_home(fm):
    with pytest.raises(FMError):
        fm.newfile("/etc/evil.txt")


@pytest.mark.orig_differs()
def test_session_restore_after_fresh_state(creds):
    c = FMClient()
    assert c.login(*creds)["error"] is False
    c.post("/actions/main/logout")  # очищает FM::session_state пользователя (ответ — редирект)
    c = FMClient()
    assert c.login(*creds)["error"] is False
    home = "/home/" + creds[0]
    for side, path in (("Left", home), ("Right", home + "/docs")):
        c.call("/actions/main/save_session", {"session": c.session(path), "order": side})
    r = c.post("/actions/main/restore_session")
    assert r.status_code == 200, r.text[:300]
    s = r.json()["data"]["session"]
    assert s["Left"]["path"] == home and s["Right"]["path"] == home + "/docs"


def test_settings_roundtrip(fm):
    d = fm.call("/actions/main/load_settings")
    assert "data" in d
