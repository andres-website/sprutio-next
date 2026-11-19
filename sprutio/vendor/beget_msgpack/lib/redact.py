# -*- coding: utf-8 -*-
"""
Маскировка паролей в логах (форк).

Аргументы RPC-вызовов логируются на INFO/DEBUG, поэтому пароли пользователей и удалённых серверов
маскируются: глобально подменяется фабрика LogRecord: итоговый текст любого сообщения проходит через redact() — для всех логгеров процесса,
включая дочерние процессы воркеров (fork наследует фабрику).
"""
import logging
import re

_KEY = r"""[\w-]*pass(?:word|wd)?"""
# 'password': b'...' | "passwd": "..." | b'sftp_password': b'...'
_QUOTED = re.compile(r"""(b?(['"])""" + _KEY + r"""\2\s*:\s*b?)(['"])(?:\\.|(?!\3).)*\3""", re.IGNORECASE)
# password=... (kwargs, query strings)
_ASSIGN = re.compile(r"""(\b""" + _KEY + r"""=)(b?['"][^'"]*['"]|[^\s&,;)}\]]+)""", re.IGNORECASE)
MASK = "***"


def redact(text):
    if not text or "pass" not in text.lower():
        return text
    text = _QUOTED.sub(lambda m: m.group(1) + m.group(3) + MASK + m.group(3), text)
    text = _ASSIGN.sub(lambda m: m.group(1) + MASK, text)
    return text


_installed = False


def install():
    """Подключить маскировку для всех логгеров процесса (идемпотентно)."""
    global _installed
    if _installed:
        return
    _installed = True
    base_factory = logging.getLogRecordFactory()

    def factory(*args, **kwargs):
        record = base_factory(*args, **kwargs)
        original = record.getMessage

        def get_message():
            try:
                return redact(original())
            except Exception:
                return original()

        record.getMessage = get_message
        return record

    logging.setLogRecordFactory(factory)
