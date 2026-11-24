"""Новый редактор (Ace 1.45) по галочке «Редактор+»: по умолчанию — родной Ace 1.2.0.

Проверка кода (ace-linters) и ИИ-подсказки серым текстом: через сервер (/fork/ai/complete → aimock стенда)
и напрямую из браузера в «Ollama» (aimock на 127.0.0.1:11435). fork_only.
"""
import json
import os

import pytest
import requests

from uihelpers import SHOTS, login
from test_ui import close_editor_discard, dbl, editor, open_path

pytestmark = pytest.mark.fork_only("новый редактор и ИИ-подсказки")

E = "ace.edit(document.querySelector('.fm-editor-window .ace_editor'))"
MOCK = "http://127.0.0.1:11435"


def mock_up():
    try:
        return requests.get(MOCK + "/api/tags", timeout=3).ok
    except requests.RequestException:
        return False


@pytest.fixture()
def next_page(page, creds, api, work):
    """Страница с включённым новым редактором; папка work открыта в левой панели."""
    def make(ai=None, lint=True):
        script = "localStorage.setItem('fm-fork-ace-next', '1');" \
                 "localStorage.setItem('fm-fork-ace-lint', %r);" % ('1' if lint else '0')
        if ai is not None:
            script += "localStorage.setItem('fm-fork-ai', %r);" % json.dumps(ai)
        page.context.add_init_script(script)
        for side in ("Left", "Right"):
            api.call("/actions/main/save_session", {"session": api.session(work), "order": side})
        login(page, creds)
        return page
    return make


def open_editor(page, name):
    dbl(page, name)
    editor(page)
    page.wait_for_function(E + ".session.getValue() !== undefined")


def test_default_is_original_ace(fm_page, js_errors):
    assert fm_page.evaluate("window.FM_ACE_NEXT") is False
    assert fm_page.evaluate("typeof window.FMAceNext") == "undefined"
    assert fm_page.evaluate("!!document.querySelector('script[src*=\"/lib/ace-builds/src-min-noconflict/ace.js\"]')")
    assert not fm_page.evaluate("!!document.querySelector('script[src*=\"ace-builds-next\"]')")
    assert js_errors == []


def test_settings_tab_switches_editor(fm_page):
    fm_page.evaluate("FM.Actions.Settings.execute()")
    win = fm_page.locator(".fm-settings-window")
    win.wait_for(timeout=10000)
    win.locator(".x-tab", has_text="Editor+").click()
    assert not fm_page.evaluate("Ext.ComponentQuery.query('checkbox[name=fm_fork_ace_next]')[0].getValue()")
    fm_page.wait_for_function("(document.querySelector('.fm-fork-ai-server-status') || {}).innerText"
                              "?.startsWith('Server: mock-coder')", timeout=10000)
    os.makedirs(SHOTS, exist_ok=True)
    win.screenshot(path=os.path.join(SHOTS, "fork-editor-plus-settings.png"))
    win.locator(".x-form-cb-label", has_text="New editor (Ace 1.45)").click()
    win.locator(".x-form-cb-label", has_text="Via the server").click()
    win.locator(".x-btn", has_text="Save").click()
    q = fm_page.locator(".x-window", has_text="Reload now?")
    q.wait_for(timeout=10000)
    with fm_page.expect_navigation(timeout=30000):
        q.locator(".x-btn", has_text="Yes").click()
    fm_page.wait_for_selector(".fm-file-list-panel .x-grid-item", timeout=45000)
    assert fm_page.evaluate("ace.version") == "1.45.2"
    assert fm_page.evaluate("JSON.parse(localStorage.getItem('fm-fork-ai')).provider") == "server"
    # и обратно — родной редактор
    fm_page.evaluate("localStorage.setItem('fm-fork-ace-next', '0')")
    fm_page.reload()
    fm_page.wait_for_selector(".fm-file-list-panel .x-grid-item", timeout=45000)
    assert fm_page.evaluate("window.FM_ACE_NEXT") is False


def test_lint_annotations(next_page, api, work, js_errors):
    api.write(work + "/broken.js", "function f() {\n  const x = ;\n  return x\n}\n")
    api.write(work + "/wrong.json", '{"a": 1,,}\n')
    page = next_page()
    assert page.evaluate("ace.version") == "1.45.2"
    open_editor(page, "broken")
    page.wait_for_function(E + ".session.getAnnotations().some(a => a.type === 'error' && a.row === 1)",
                           timeout=30000)
    assert page.locator(".fm-editor-window .ace_gutter-cell.ace_error").count() >= 1
    close_editor_discard(page)
    open_editor(page, "wrong")
    page.wait_for_function(E + ".session.getAnnotations().some(a => a.type === 'error')", timeout=30000)
    close_editor_discard(page)
    assert [e for e in js_errors if "unload" not in e] == []


def test_emmet_and_save_in_new_editor(next_page, api, work):
    api.newfile(work + "/e.html")
    page = next_page()
    open_editor(page, "e")
    assert page.evaluate(E + ".getOption('enableEmmet')")
    page.locator(".fm-editor-window .ace_text-input").focus()
    page.keyboard.type("ul>li*2")
    page.keyboard.press("Tab")
    assert page.evaluate(E + ".getValue()").count("<li></li>") == 2
    page.keyboard.press("Control+s")
    page.wait_for_function("!document.querySelector('.fm-editor-window').innerText.includes('Modified')",
                           timeout=10000)
    page.wait_for_timeout(500)
    assert api.read(work + "/e.html")["content"].count("<li></li>") == 2
    close_editor_discard(page)


def _type_and_wait_ghost(page):
    page.evaluate(E + ".navigateFileEnd()")
    page.locator(".fm-editor-window .ace_text-input").focus()
    page.keyboard.type("\nfunction add(a, b) {")
    page.keyboard.press("Enter")
    page.keyboard.type("return ")
    page.wait_for_selector(".fm-editor-window .ace_ghost_text", timeout=15000)
    return page.locator(".fm-editor-window .ace_ghost_text").inner_text()


@pytest.mark.parametrize("ai", [
    {"provider": "server", "auto": True, "delay": 300},
    {"provider": "ollama", "auto": True, "delay": 300, "ollamaUrl": MOCK.replace("127.0.0.1", "localhost"),
     "ollamaModel": "mock-coder"},
], ids=["server", "ollama-direct"])
def test_ai_ghost_text_accept(next_page, api, work, ai):
    if not mock_up():
        pytest.skip("aimock не запущен")
    api.write(work + "/ghost.js", "// test\n")
    page = next_page(ai=ai, lint=False)
    open_editor(page, "ghost")
    assert _type_and_wait_ghost(page).strip() == "a + b;"
    assert "Tab" in page.locator(".fm-editor-window .fm-ai-status").inner_text()
    os.makedirs(SHOTS, exist_ok=True)
    page.locator(".fm-editor-window").screenshot(path=os.path.join(SHOTS, "fork-ai-ghost-%s.png" % ai["provider"]))
    page.keyboard.press("Tab")
    value = page.evaluate(E + ".getValue()")
    assert "return a + b;" in value
    page.wait_for_selector(".fm-editor-window .ace_ghost_text", state="detached", timeout=5000)
    last = requests.get(MOCK + "/_last", timeout=5).json()
    assert last["path"] == ("/v1/completions" if ai["provider"] == "server" else "/api/generate")
    assert last["body"]["prompt"].endswith("return ")
    close_editor_discard(page)


def test_ai_dismiss_and_plain_tab(next_page, api, work):
    if not mock_up():
        pytest.skip("aimock не запущен")
    api.write(work + "/dismiss.js", "// test\n")
    page = next_page(ai={"provider": "server", "auto": True, "delay": 300}, lint=False)
    open_editor(page, "dismiss")
    _type_and_wait_ghost(page)
    page.keyboard.press("Escape")
    # Ace перерисовывает текст асинхронно (requestAnimationFrame) — ждём исчезновения
    page.wait_for_selector(".fm-editor-window .ace_ghost_text", state="detached", timeout=5000)
    assert page.locator(".fm-editor-window").count() == 1          # Esc не закрыл окно редактора
    before = page.evaluate(E + ".getValue()")
    page.keyboard.press("Tab")                                       # без подсказки Tab — обычный отступ
    after = page.evaluate(E + ".getValue()")
    assert after != before and "a + b" not in after
    close_editor_discard(page)


def test_ai_manual_only(next_page, api, work):
    if not mock_up():
        pytest.skip("aimock не запущен")
    api.write(work + "/manual.js", "// test\n")
    page = next_page(ai={"provider": "server", "auto": False}, lint=False)
    open_editor(page, "manual")
    page.evaluate(E + ".navigateFileEnd()")
    page.locator(".fm-editor-window .ace_text-input").focus()
    page.keyboard.type("\nreturn ")
    page.wait_for_timeout(1500)
    assert page.locator(".fm-editor-window .ace_ghost_text").count() == 0
    page.keyboard.press("Alt+\\")
    page.wait_for_selector(".fm-editor-window .ace_ghost_text", timeout=15000)
    close_editor_discard(page)
