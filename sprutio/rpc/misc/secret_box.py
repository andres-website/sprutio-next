# -*- coding: utf-8 -*-
"""
Шифрование паролей удалённых серверов (FTP/SFTP/WebDAV) в rpc.db (форк).

Ключ Fernet хранится в файле, доступном только root (FM_RPC_SECRET_FILE, по умолчанию
/var/spool/fm/secret.key — постоянный том rpc). Ключ загружается в память процесса rpc при старте (load()),
воркеры получают его по наследству через fork до сброса прав (setuid) — после сброса файл им не прочитать.
Значения в БД: "fm1:<fernet-token>". Старые незашифрованные значения читаются как есть и шифруются миграцией.
"""
import os

from cryptography.fernet import Fernet

PREFIX = "fm1:"
KEY_FILE = os.getenv("FM_RPC_SECRET_FILE", "/var/spool/fm/secret.key")

_fernet = None


def load(create=True):
    """Прочитать (или создать) ключ. Вызывать от root до запуска воркеров."""
    global _fernet
    if _fernet is not None:
        return _fernet
    env_key = os.getenv("FM_RPC_SECRET_KEY")
    if env_key:
        key = env_key.encode()
    elif os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            key = f.read().strip()
    elif create:
        key = Fernet.generate_key()
        os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
        fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(key)
    else:
        raise RuntimeError("secret key file %s not found" % KEY_FILE)
    _fernet = Fernet(key)
    return _fernet


def _text(value):
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def is_encrypted(value):
    value = _text(value)
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt(value):
    value = _text(value)
    if value is None or is_encrypted(value):
        return value
    return PREFIX + load().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(value):
    value = _text(value)
    if not is_encrypted(value):
        return value  # значение без шифрования (до миграции)
    return load().decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
