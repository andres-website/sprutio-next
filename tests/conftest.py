"""Общие настройки тестов.

Маркер orig_differs — поведение форка отличается от оригинального sprutio.
  FM_STACK=orig  → тест ожидаемо падает (xfail strict: если вдруг пройдёт — сигнал;
                   orig_differs(strict=False) — для недетерминированных случаев);
  иначе (форк)   → тест обязан проходить.
"""
import os

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "orig_differs: поведение форка отличается от оригинала")
    config.addinivalue_line("markers", "fork_only(reason): новая возможность форка — на оригинале пропускается")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("FM_STACK") != "orig":
        return
    for item in items:
        f = item.get_closest_marker("fork_only")
        if f:
            item.add_marker(pytest.mark.skip(reason="только форк: " + (f.args[0] if f.args else "")))
            continue
        m = item.get_closest_marker("orig_differs")
        if m:
            item.add_marker(pytest.mark.xfail(strict=m.kwargs.get("strict", True),
                                               reason="orig: " + (m.args[0] if m.args else "")))
