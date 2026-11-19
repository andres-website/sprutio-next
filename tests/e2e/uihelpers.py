import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
from fmclient import BASE  # noqa: E402

SHOTS = os.path.join(os.path.dirname(__file__), "screenshots")


def _login_once(page, creds, timeout):
    page.goto(BASE + "/")
    page.fill("#input-login", creds[0])
    page.fill("#input-password", creds[1])
    page.keyboard.press("Enter")
    page.wait_for_selector(".fm-file-list-panel .x-grid-item", timeout=timeout)
    if os.environ.get("FM_DEV") is not None:
        # FM_DEV=1 — фронт из исходников (bootstrap.js), FM_DEV=0 — явно production-сборка
        page.goto(BASE + "/?dev=" + os.environ["FM_DEV"])
        page.wait_for_selector(".fm-file-list-panel .x-grid-item", timeout=timeout)
    # дождаться, пока обе панели загрузят листинг
    page.wait_for_function("[...document.querySelectorAll('.fm-pathbar')].filter(b => "
                           "((b.querySelector('input.fm-path-input') || {}).value || b.innerText).trim()).length >= 2",
                           timeout=timeout)


def login(page, creds):
    # первая загрузка UI после рестарта стенда бывает долгой — одна повторная попытка
    try:
        _login_once(page, creds, 45000)
    except Exception:
        os.makedirs(SHOTS, exist_ok=True)
        page.screenshot(path=os.path.join(SHOTS, "login-retry.png"))
        with open(os.path.join(SHOTS, "login-retry.html"), "w") as f:
            f.write(page.content())
        page.context.clear_cookies()
        _login_once(page, creds, 60000)
