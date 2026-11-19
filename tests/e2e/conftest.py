import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
from fmclient import FMClient  # noqa: E402
from uihelpers import login  # noqa: E402,F401



def _env():
    env = {}
    with open(os.path.join(os.path.dirname(__file__), "..", "..", "stand", ".env")) as f:
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
def api(creds):
    c = FMClient()
    assert c.login(*creds)["error"] is False
    c.init_session()
    return c


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "ignore_https_errors": True, "viewport": {"width": 1440, "height": 900},
            "locale": "en-US"}


@pytest.fixture()
def js_errors(page):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    return errors


@pytest.fixture()
def fm_page(page, creds, api):
    # Обе панели начинают в домашнем каталоге (сессия панелей хранится на сервере)
    for side in ("Left", "Right"):
        api.call("/actions/main/save_session", {"session": api.session(api.home), "order": side})
    login(page, creds)
    return page


@pytest.fixture()
def work(api):
    path = "%s/e2e-%s" % (api.home, uuid.uuid4().hex[:6])
    api.mkdir(path)
    yield path
    try:
        api.remove([path])
    except Exception:
        pass
