"""Скриншоты фронт-дополнений форка для ручной проверки: venv/bin/python tests/e2e/shots_fork.py"""
import os
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(__file__))
from conftest import _env  # noqa: E402
from uihelpers import SHOTS, login  # noqa: E402

e = _env()
creds = (e["FM_TEST_USER"], e["FM_TEST_PASS"])
os.makedirs(SHOTS, exist_ok=True)

with sync_playwright() as pw:
    b = pw.chromium.launch()
    for dpr in (1, 2):
        ctx = b.new_context(ignore_https_errors=True, viewport={"width": 1280, "height": 640},
                            device_scale_factor=dpr, locale="ru-RU")
        p = ctx.new_page()
        login(p, creds)
        p.evaluate("FM.Actions.Open.execute(FM.Left, FM.Left.session.path + '/site')")
        p.wait_for_timeout(1500)
        p.screenshot(path=os.path.join(SHOTS, "fork-pathbar-dpr%d.png" % dpr))
        if dpr == 1:
            p.locator(".fm-file-list-panel >> nth=0").locator(".x-grid-item").first.click()
            p.keyboard.press("Control+l")
            p.wait_for_timeout(300)
            p.screenshot(path=os.path.join(SHOTS, "fork-pathbar-edit.png"), clip={"x": 0, "y": 0, "width": 1280, "height": 200})
            p.keyboard.press("Escape")
            p.evaluate("""() => { const el = FM.Right.filelist.getView().el.dom; const dt = new DataTransfer();
                dt.items.add(new File(['x'], 'a.txt')); const r = el.getBoundingClientRect();
                el.dispatchEvent(new DragEvent('dragenter', {dataTransfer: dt, bubbles: true}));
                el.dispatchEvent(new DragEvent('dragover', {dataTransfer: dt, bubbles: true, cancelable: true,
                  clientX: r.x + 50, clientY: r.y + 50})); }""")
            p.wait_for_timeout(300)
            p.screenshot(path=os.path.join(SHOTS, "fork-drop-overlay.png"))
        else:
            p.locator(".fm-file-list-panel >> nth=1").screenshot(path=os.path.join(SHOTS, "fork-panel-dpr2.png"))
        ctx.close()
    b.close()
print("ok")
