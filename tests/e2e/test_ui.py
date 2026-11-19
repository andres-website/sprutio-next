"""E2E-тесты интерфейса sprutio (Playwright, headless Chromium на VPS).

Эталон снят на оригинальном фронте (ExtJS 5.1.1). Запуск: stand/run-tests.sh e2e
"""
import os

from uihelpers import SHOTS, login

ACTIVE = ".fm-panel-active"


def rows(page, panel=ACTIVE):
    return page.eval_on_selector_all(panel + " .x-grid-item",
                                     "els => els.map(e => e.querySelector('td').innerText.trim())")


def open_path(page, path, side="Left"):
    page.evaluate("([s, p]) => FM.Actions.Open.execute(FM[s], p)", [side, path])
    page.wait_for_function("p => (b => (b.querySelector('input.fm-path-input') || {}).value || b.innerText)(document.querySelector('.fm-panel-active .fm-pathbar')).replace(/^\\.\\./, '').endsWith(p.split('/').pop())",
                           arg=path, timeout=15000)


def dbl(page, name, panel=ACTIVE):
    page.locator(panel + " .x-grid-item td:first-child", has_text=name).first.dblclick()


def editor(page):
    page.wait_for_selector(".fm-editor-window .ace_editor", timeout=15000)
    return page.locator(".fm-editor-window").last


def ace_value(page):
    return page.evaluate("ace.edit(document.querySelector('.fm-editor-window .ace_editor')).getValue()")


def close_editor_discard(page):
    page.evaluate("Ext.getCmp(document.querySelector('.fm-editor-window').id).close()")
    q = page.locator(".x-window", has_text="File Modified")
    if q.count():
        q.locator(".x-btn", has_text="No").click()
    page.wait_for_selector(".fm-editor-window", state="detached", timeout=10000)


# ---------------------------------------------------------------------------

def test_login_page(page):
    from fmclient import BASE
    page.goto(BASE + "/")
    assert page.title() == "SPRUT.io"
    assert page.is_visible("#input-login") and page.is_visible("#input-password")


def test_two_panels_home(fm_page, js_errors, api):
    panels = fm_page.locator(".fm-file-list-panel")
    assert panels.count() == 2
    bars = fm_page.eval_on_selector_all(".fm-pathbar", "els => els.map((b => (b.querySelector('input.fm-path-input') || {}).value || b.innerText))")
    assert bars == [api.home, api.home]
    for p in (".fm-file-list-panel >> nth=0", ".fm-file-list-panel >> nth=1"):
        names = fm_page.locator(p).locator(".x-grid-item td:first-child").all_inner_texts()
        assert {"docs", "site"} <= {n.strip() for n in names}
    os.makedirs(SHOTS, exist_ok=True)
    fm_page.screenshot(path=os.path.join(SHOTS, "home-dpr1.png"))
    assert js_errors == []


def test_navigate_dblclick_and_breadcrumb(fm_page, api):
    dbl(fm_page, "site")
    fm_page.wait_for_function("(b => (b.querySelector('input.fm-path-input') || {}).value || b.innerText)(document.querySelector('.fm-panel-active .fm-pathbar')).endsWith('/site')")
    assert {"..", "css", "index"} <= set(rows(fm_page))
    # клик по хлебной крошке возвращает в домашний каталог
    fm_page.locator(ACTIVE + " .fm-pathbar span", has_text=api.home.split("/")[-1]).click()
    fm_page.wait_for_function("p => (b => (b.querySelector('input.fm-path-input') || {}).value || b.innerText)(document.querySelector('.fm-panel-active .fm-pathbar')) === p",
                              arg=api.home)


def test_go_up_with_dotdot(fm_page, api):
    dbl(fm_page, "docs")
    fm_page.wait_for_function("(b => (b.querySelector('input.fm-path-input') || {}).value || b.innerText)(document.querySelector('.fm-panel-active .fm-pathbar')).endsWith('/docs')")
    dbl(fm_page, "..")
    fm_page.wait_for_function("p => (b => (b.querySelector('input.fm-path-input') || {}).value || b.innerText)(document.querySelector('.fm-panel-active .fm-pathbar')) === p",
                              arg=api.home)


def test_editor_opens_with_highlight(fm_page):
    dbl(fm_page, "site")
    fm_page.wait_for_function("(b => (b.querySelector('input.fm-path-input') || {}).value || b.innerText)(document.querySelector('.fm-panel-active .fm-pathbar')).endsWith('/site')")
    dbl(fm_page, "index")
    win = editor(fm_page)
    assert "index.html" in win.locator(".x-title-text").first.inner_text()
    assert "Привет, sprutio" in ace_value(fm_page)
    assert fm_page.evaluate("ace.edit(document.querySelector('.fm-editor-window .ace_editor')).session.getMode().$id") \
        == "ace/mode/html"
    assert win.locator(".ace_tag-name").count() > 0  # подсветка разметки
    close_editor_discard(fm_page)


def test_editor_emmet_tab_and_save(fm_page, api, work):
    api.newfile(work + "/e.html")
    open_path(fm_page, work)
    dbl(fm_page, "e")
    editor(fm_page)
    assert fm_page.evaluate("ace.edit(document.querySelector('.fm-editor-window .ace_editor')).getOption('enableEmmet')")
    fm_page.locator(".fm-editor-window .ace_text-input").focus()
    fm_page.keyboard.type("ul>li*2")
    fm_page.keyboard.press("Tab")
    val = ace_value(fm_page)
    assert val.count("<li></li>") == 2 and "<ul>" in val
    fm_page.keyboard.press("Control+s")
    fm_page.wait_for_function("document.querySelector('.fm-editor-window').innerText.includes('Saved') || "
                              "!document.querySelector('.fm-editor-window').innerText.includes('Modified')",
                              timeout=10000)
    fm_page.wait_for_timeout(1000)
    assert api.read(work + "/e.html")["content"].count("<li></li>") == 2
    close_editor_discard(fm_page)


def test_upload_dialog_opens(fm_page):
    fm_page.locator(".x-btn", has_text="Upload Files").first.click()
    fm_page.wait_for_selector(".x-window.fm-upload-dialog, .x-window:has-text('Upload')", timeout=10000)
    fm_page.keyboard.press("Escape")


def test_drop_handler(fm_page):
    """Эталон: в оригинале нет обработчиков drop на панелях; в форке drop перехватывается (загрузка)."""
    has = fm_page.evaluate("""() => {
        const el = document.querySelector('.fm-file-list-panel .x-grid-view');
        const dt = new DataTransfer();
        const ev = new DragEvent('dragover', {dataTransfer: dt, bubbles: true, cancelable: true});
        dt.items.add(new File(['x'], 'dnd.txt'));
        el.dispatchEvent(ev); return ev.defaultPrevented; }""")
    assert has is (os.environ.get("FM_STACK") != "orig")


def test_retina_screenshot(browser, creds, api):
    """Снимки для сравнения чёткости иконок: devicePixelRatio=2 (не проверка, а артефакт)."""
    ctx = browser.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 900},
                              device_scale_factor=2, locale="en-US")
    p = ctx.new_page()
    login(p, creds)
    os.makedirs(SHOTS, exist_ok=True)
    p.screenshot(path=os.path.join(SHOTS, "home-dpr2.png"))
    p.locator(".fm-file-list-panel").first.screenshot(path=os.path.join(SHOTS, "panel-dpr2.png"))
    ctx.close()


def test_logout(fm_page):
    if os.environ.get("FM_STACK") != "orig":
        # форк: верхнее меню закрыто полосой с инпутами пути — выдвигаем его кнопкой ▾
        fm_page.locator(".fm-fork-menu-toggle").click()
    fm_page.locator(".x-btn", has_text="Logout").first.click()
    fm_page.wait_for_url("**/login**", timeout=15000)


def test_fast_search_checkbox(fm_page):
    """Форк: галочка «Быстрый поиск» в окне поиска по содержимому, флаг fast уходит в запрос."""
    import json as _json
    import pytest as _pytest
    if __import__("os").environ.get("FM_STACK") == "orig":
        _pytest.skip("только форк")
    sent = []
    fm_page.on("request", lambda r: sent.append(r.post_data) if r.url.endswith("/actions/find/text") else None)
    fm_page.locator(".x-btn", has_text="Search Text").first.click()
    fm_page.wait_for_selector("input[name=search-file-text]", timeout=10000)
    cb = fm_page.locator(".x-form-cb-label", has_text="Fast search").first
    assert cb.is_visible()
    fm_page.fill("input[name=search-file-text]", "Привет")
    if not fm_page.evaluate("Ext.ComponentQuery.query('checkbox[name=search-fast]')[0].getValue()"):
        cb.click()
    win = fm_page.locator(".x-window", has=fm_page.locator("input[name=search-file-text]"))
    win.locator(".x-btn", has_text="Search").last.click()
    fm_page.wait_for_function(
        "() => { const w = Ext.ComponentQuery.query('textfield[name=search-file-text]')[0].up('window');"
        " return w.down('grid').getStore().getCount() > 0; }", timeout=20000)
    names = fm_page.evaluate("Ext.ComponentQuery.query('textfield[name=search-file-text]')[0].up('window')"
                             ".down('grid').getStore().getRange().map(r => r.get('name'))")
    assert "index.html" in names
    assert sent and _json.loads(sent[0])["params"].get("fast") is True
