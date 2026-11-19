# -*- coding: utf-8 -*-
"""
Экспериментальный быстрый поиск (форк). Включается параметром {"fast": true} в params поиска
(галочка «Быстрый поиск» в окнах поиска).

Оригинальный поиск обходит дерево сам (по SFTP — запросом на каждую папку) и для поиска по содержимому
читает каждый файл в Python, по SFTP — скачивая его целиком. Быстрый поиск отдаёт работу утилитам там,
где лежат файлы:
  - домашний сервер: ripgrep (rg) / GNU find в контейнере rpc — запускаются ПОСЛЕ сброса прав (от имени
    пользователя), т.е. видят ровно то же, что и оригинальный поиск;
  - SFTP: одна команда по SSH на удалённом сервере (rg, если установлен, иначе GNU grep / find).
Если быстрый способ недоступен (нет shell у SFTP-аккаунта, BusyBox без нужных ключей и т.п.) —
FastSearchUnavailable, вызывающий код откатывается на оригинальный поиск.

Семантика совпадает с оригиналом:
  - по содержимому: без учёта регистра, подстановки * ? [..] как в fnmatch, двоичные файлы пропускаются,
    скрытые файлы и .gitignore не исключаются;
  - по имени: fnmatch-шаблон с учётом регистра, файлы и/или папки, фильтр размера только для файлов.
"""
import os
import shlex
import shutil
import subprocess
import time

from misc.helpers import fnmatch_body

WILDCARDS = set("*?[")
OUTPUT_LIMIT = 64 * 1024 * 1024  # защита от гигантского вывода


class FastSearchUnavailable(Exception):
    pass


def text_pattern(text):
    """('fixed', text) для обычной строки, ('regex', выражение) для шаблона с подстановками."""
    if WILDCARDS & set(text):
        return "regex", fnmatch_body(text)
    return "fixed", text


def _split0(data):
    return [p for p in data.decode("utf-8", "surrogateescape").split("\0") if p]


# --- локально (домашний сервер) -----------------------------------------------------------------------

def _run_local(cmd, timeout):
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except FileNotFoundError:
        raise FastSearchUnavailable("%s not found" % cmd[0])
    # 0 — найдено, 1 — не найдено, 2 — были ошибки доступа к части файлов (результат всё равно полезен)
    if proc.returncode not in (0, 1, 2):
        raise FastSearchUnavailable("%s exited %s: %s" % (cmd[0], proc.returncode, proc.stderr[:300]))
    return _split0(proc.stdout)


def local_find_text(abs_path, text, timeout):
    mode, pattern = text_pattern(text)
    rg = shutil.which("rg")
    if rg:
        cmd = [rg, "-l", "-0", "-i", "--hidden", "--no-ignore", "--no-messages"]
        if mode == "fixed":
            cmd.append("-F")
        cmd += ["-e", pattern, "--", abs_path]
        engine = "rg"
    else:
        cmd = ["grep", "-r", "-l", "-Z", "-I", "-i", "-F" if mode == "fixed" else "-P", "-e", pattern, "--",
               abs_path]
        engine = "grep"
    return engine, _run_local(cmd, timeout)


def find_args(path, filename, type_file, type_dir, file_size, size_direction):
    """Аргументы GNU find: те же условия, что в оригинальном findFiles."""
    branches = []
    if type_file:
        branch = ["-type", "f", "-name", filename]
        if file_size:
            n = int(file_size)
            # оригинал: size >= N ('more') или size <= N ('less'); -size +Nc означает строго больше
            branch += ["-size", ("+%dc" % (n - 1)) if size_direction == "more" else ("-%dc" % (n + 1))]
        branches.append(branch)
    if type_dir:
        branches.append(["-type", "d", "-name", filename])
    if not branches:
        return None
    expr = []
    for i, b in enumerate(branches):
        if i:
            expr.append("-o")
        expr += ["("] + b + [")"]
    return ["find", path, "-mindepth", "1", "("] + expr + [")", "-print0"]


def local_find_files(abs_path, filename, type_file, type_dir, file_size, size_direction, timeout):
    args = find_args(abs_path, filename, type_file, type_dir, file_size, size_direction)
    if args is None:
        return "find", []
    return "find", _run_local(args, timeout)


# --- удалённо по SSH (SFTP-подключение) ---------------------------------------------------------------

def _run_remote(ssh, command, timeout):
    """Выполнить команду на сервере, прочитать stdout потоком (без зависания на большом выводе)."""
    if not ssh.is_connected:
        ssh.connect()
    try:
        transport = ssh.ssh.get_transport()
        chan = transport.open_session(timeout=30)
        chan.settimeout(5.0)
        chan.exec_command("export LC_ALL=C; " + command)
    except Exception as e:
        raise FastSearchUnavailable("ssh exec failed: %s" % e)

    out, err = bytearray(), bytearray()
    deadline = time.time() + timeout
    while True:
        if time.time() > deadline:
            chan.close()
            raise TimeoutError("fast search timeout")
        if chan.recv_ready():
            out += chan.recv(1 << 20)
            if len(out) > OUTPUT_LIMIT:
                chan.close()
                raise FastSearchUnavailable("output too large")
            continue
        if chan.recv_stderr_ready():
            err += chan.recv_stderr(1 << 16)
            continue
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.01)
    code = chan.recv_exit_status()
    chan.close()
    return code, bytes(out), bytes(err).decode("utf-8", "replace")


def _check_remote(code, err, what):
    if code in (0, 1, 2):
        return
    # 126/127 — нет команды или shell запрещён (ForceCommand internal-sftp и т.п.)
    raise FastSearchUnavailable("remote %s exited %s: %s" % (what, code, err[:300]))


def _remote_has_nul(ssh, path, size=8192):
    """Признак двоичного файла как у GNU grep -I / ripgrep: нулевой байт в начале файла."""
    try:
        with ssh.sftp.file(path, "rb") as f:
            return b"\0" in f.read(size)
    except IOError:
        return True


def remote_find_text(ssh, path, text, timeout):
    """rg → GNU grep → BusyBox grep (без -Z и без пропуска двоичных: фильтруем двоичные отдельно)."""
    mode, pattern = text_pattern(text)
    q_path, q_pat = shlex.quote(path), shlex.quote(pattern)
    rg_flags = "-l0i --hidden --no-ignore --no-messages" + (" -F" if mode == "fixed" else "")
    gnu_flags = "-rlZIi " + ("-F" if mode == "fixed" else "-E")
    bb_flags = "-rli " + ("-F" if mode == "fixed" else "-E")
    script = (
        "if command -v rg >/dev/null 2>&1; then echo rg >&2; rg {rg} -e {pat} -- {path}; "
        "elif grep -Z -I -q x /dev/null 2>/dev/null; [ $? -ne 2 ]; then echo grep >&2; grep {gnu} -e {pat} -- {path}; "
        "else echo busybox >&2; grep {bb} -e {pat} -- {path}; fi"
    ).format(rg=rg_flags, gnu=gnu_flags, bb=bb_flags, pat=q_pat, path=q_path)
    code, out, err = _run_remote(ssh, script, timeout)
    engine = err.split("\n", 1)[0].strip()
    if engine not in ("rg", "grep", "busybox"):
        # shell не выполнил скрипт (синтаксис, запрещённый shell и т.п.) — молча отдавать пусто нельзя
        raise FastSearchUnavailable("remote shell error: %s" % err[:300])
    _check_remote(code, err, engine)
    if engine == "busybox":
        paths = [p for p in out.decode("utf-8", "surrogateescape").split("\n") if p]
        # BusyBox grep не пропускает двоичные файлы — как оригинал, отсеиваем их (найденных обычно мало)
        paths = [p for p in paths if not _remote_has_nul(ssh, p)]
        return "busybox-grep", paths
    return engine, _split0(out)


def remote_find_files(ssh, path, filename, type_file, type_dir, file_size, size_direction, timeout):
    args = find_args(path, filename, type_file, type_dir, file_size, size_direction)
    if args is None:
        return "find", []
    code, out, err = _run_remote(ssh, " ".join(shlex.quote(a) for a in args), timeout)
    if "unknown predicate" in err or "invalid" in err:
        raise FastSearchUnavailable("remote find: %s" % err[:200])
    _check_remote(code, err, "find")
    return "find", _split0(out)


def describe(engine, started):
    return "%s, %.2fs" % (engine, time.time() - started)


def strip_root(paths, root_mount):
    """Абсолютные пути контейнера (/mnt/...) → пути пользователя (/...)."""
    root = root_mount.rstrip("/")
    return [("/" + p[len(root):].lstrip("/")) if p.startswith(root + "/") else p for p in paths]


def basename_ok(path):
    return bool(os.path.basename(path.rstrip("/")))
