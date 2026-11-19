"""Тонкий клиент к HTTP API sprutio (app/handlers). Используется характеризационными тестами."""
import json
import os
import time

import requests
import urllib3

urllib3.disable_warnings()

BASE = os.environ.get("FM_BASE", "https://127.0.0.1:9443")
TERMINAL = {"success", "error", "abort"}


class FMError(AssertionError):
    pass


class FMClient:
    def __init__(self, base=BASE):
        self.base = base.rstrip("/")
        self.s = requests.Session()
        self.s.verify = False
        self.s.headers["X-Requested-With"] = "XMLHttpRequest"
        self.home = None

    # --- auth -------------------------------------------------------------
    def login(self, user, password, language="en"):
        r = self.s.post(self.base + "/auth", data={"login": user, "password": password, "language": language},
                        allow_redirects=False, timeout=30)
        try:
            data = r.json()
        except ValueError:
            # При неверном пароле сервер отвечает 302 на /login вместо JSON. Нормализуем к {"error": True}.
            if r.status_code in (302, 403):
                return {"error": True, "http": r.status_code}
            raise FMError("auth: non-json %s %r" % (r.status_code, r.text[:200]))
        return data

    # --- low level ----------------------------------------------------------
    def post(self, url, payload=None, timeout=60):
        r = self.s.post(self.base + url, data=json.dumps(payload) if payload is not None else "null",
                        allow_redirects=False, timeout=timeout)
        return r

    def call(self, url, payload=None, timeout=60):
        r = self.post(url, payload, timeout)
        if r.status_code != 200:
            raise FMError("%s -> HTTP %s %r" % (url, r.status_code, r.text[:300]))
        data = r.json()
        if isinstance(data, dict) and data.get("error"):
            raise FMError("%s -> error: %r" % (url, data.get("message")))
        return data

    def session(self, path=None):
        return {"host": "localhost", "type": "home", "path": path or self.home,
                "is_share": False, "is_share_write": False}

    # --- operations ---------------------------------------------------------
    def init_session(self, path=None):
        """Открыть сессию в домашнем каталоге песочницы (/home/<user>).
        Не берём путь из restore_session: там последняя папка панелей, сохранённая UI."""
        if path is None:
            path = "/home/" + self.call("/actions/home/init_callback")["data"]["account"]["login"]
        d = self.call("/actions/main/init_session", {"session": self.session(path)})["data"]
        self.home = d["session"]["path"]
        return d

    def ls(self, path):
        d = self.call("/actions/files/list", {"path": path, "session": self.session(path)})
        return {i["name"]: i for i in d["data"]["items"]}

    def wait(self, status, path=None, timeout=60):
        """Опрос /actions/main/check_status до финального статуса (как ProgressWindow во фронте)."""
        deadline = time.time() + timeout
        while status.get("status") not in TERMINAL:
            if time.time() > deadline:
                raise FMError("operation timeout: %r" % status)
            time.sleep(0.5)
            status = self.call("/actions/main/check_status",
                               {"session": self.session(path), "status": status})["data"]
        return status

    def op(self, url, payload, path=None, timeout=60):
        st = self.call(url, payload)["data"]
        st = self.wait(st, path, timeout)
        if st.get("status") != "success":
            raise FMError("%s finished with %r" % (url, st))
        return st

    def mkdir(self, path):
        return self.call("/actions/files/mkdir", {"path": path, "session": self.session()})

    def newfile(self, path):
        return self.call("/actions/files/newfile", {"path": path, "session": self.session()})

    def write(self, path, content, encoding="utf-8"):
        return self.call("/actions/files/write",
                         {"path": path, "content": content, "encoding": encoding, "session": self.session()})

    def read(self, path, encoding=None):
        return self.call("/actions/files/read", {"path": path, "encoding": encoding, "session": self.session()})["data"]

    def rename(self, src, dst):
        return self.call("/actions/files/rename", {"source_path": src, "target_path": dst, "session": self.session()})

    def remove(self, paths):
        return self.op("/actions/files/remove", {"paths": paths, "session": self.session(self.parent(paths[0]))})

    @staticmethod
    def parent(path):
        return path.rsplit("/", 1)[0] or "/"

    # Как во фронте: session.path = текущая папка панели, т.е. родитель выделенных элементов.
    def copy(self, paths, target, overwrite=False):
        return self.op("/actions/files/copy", {"paths": paths, "target": self.session(target),
                                               "overwrite": overwrite, "session": self.session(self.parent(paths[0]))})

    def move(self, paths, target, overwrite=False):
        return self.op("/actions/files/move", {"paths": paths, "target": self.session(target),
                                               "overwrite": overwrite, "session": self.session(self.parent(paths[0]))})

    def create_copy(self, paths):
        return self.op("/actions/files/create_copy", {"paths": paths, "session": self.session(self.parent(paths[0]))})

    def chmod(self, paths, code, recursive=False):
        return self.op("/actions/files/chmod", {"params": {"paths": [{"path": p} for p in paths], "code": code,
                                                           "recursive": recursive, "recursive_mode": "all"},
                                                "session": self.session(self.parent(paths[0]))})

    def archive_create(self, path, files, typ="zip"):
        """path — без расширения: сервер сам добавляет .zip/.tar.gz/.tar.bz2/.tar (как CreateArchiveWindow)."""
        name = path.rsplit("/", 1)[1]
        return self.op("/actions/archive/create", {"params": {"path": path, "type": typ, "archive_name": name,
                                                              "files": [{"path": p} for p in files]},
                                                   "session": self.session(self.parent(files[0]))}, timeout=120)

    def archive_extract(self, archive, extract_path):
        return self.op("/actions/archive/extract", {"params": {"file": {"path": archive}, "extract_path": extract_path},
                                                    "session": self.session()}, timeout=120)

    def find_files(self, path, filename):
        return self.op("/actions/find/files", {"params": {"path": path, "filename": filename, "file_size": 0,
                                                          "type_dir": True, "type_file": True,
                                                          "size_direction": "more"},
                                               "session": self.session()})

    def find_text(self, path, text):
        return self.op("/actions/find/text", {"params": {"path": path, "text": text}, "session": self.session()})

    def analyze_size(self, path):
        return self.op("/actions/files/analyze_size", {"path": path, "session": self.session()})

    def upload(self, dir_path, name, data, overwrite=False):
        r = self.s.post(self.base + "/upload",
                        params={"overwrite": "true" if overwrite else "false", "session": json.dumps(self.session(dir_path))},
                        data=data, headers={"X-File-Name": name, "Content-Type": "application/octet-stream"},
                        timeout=60)
        if r.status_code != 200:
            raise FMError("upload HTTP %s %r" % (r.status_code, r.text[:300]))
        return r

    def download(self, paths, mode="default"):
        return self.s.post(self.base + "/actions/files/download",
                           data={"session": json.dumps(self.session()), "paths": json.dumps(paths), "mode": mode},
                           timeout=60)
