import os
import uuid

import pytest

from fmclient import FMClient


def _env():
    env = {}
    path = os.path.join(os.path.dirname(__file__), "..", "..", "stand", ".env")
    with open(path) as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                env[k] = v
    return env


@pytest.fixture(scope="session")
def creds():
    e = _env()
    return e["FM_TEST_USER"], e["FM_TEST_PASS"]


@pytest.fixture(scope="session")
def fm(creds):
    c = FMClient()
    data = c.login(*creds)
    assert data.get("error") is False, data
    c.init_session()
    return c


@pytest.fixture()
def work(fm):
    """Чистая рабочая папка в домашнем каталоге тестового пользователя, удаляется после теста."""
    path = "%s/t-%s" % (fm.home, uuid.uuid4().hex[:8])
    fm.mkdir(path)
    yield path
    try:
        fm.remove([path])
    except Exception:
        pass
