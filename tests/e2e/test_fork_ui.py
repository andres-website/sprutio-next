"""E2E: фронт-дополнения форка (fm-fork.js/css) — строка пути (инпуты над меню + «Весь путь»), загрузка перетаскиванием, retina.

На оригинале пропускаются (fork_only).
"""
import os
import time

import pytest

from uihelpers import SHOTS, login

pytestmark = pytest.mark.fork_only("фронт-дополнения форка")

ACTIVE = ".fm-panel-active"


def side(page):
    return page.evaluate("FM.Active.toString()")


def inp(page, s=None):
    return page.locator("#fm-fork-path-" + (s or side(page)))


def wait_input(page, path, s=None):
    page.wait_for_function("([s, p]) => document.getElementById('fm-fork-path-' + (s || FM.Active.toString())).value === p",
                           arg=[s, path], timeout=15000)


def crumbs_text(page):
    return page.evaluate("document.querySelector('.fm-panel-active .fm-pathbar').innerText")


def test_original_breadcrumbs_kept(fm_page, api):
    """Хлебные крошки на панелях — оригинальные (span с onclick), в них нет инпутов форка."""
    assert crumbs_text(fm_page) == api.home
    assert fm_page.locator(".fm-pathbar input").count() == 0
    assert fm_page.locator(".fm-panel-active .fm-pathbar span[onclick]").count() >= 2


def test_top_inputs_over_main_menu(fm_page, api):
    """Два инпута поверх верхней полосы меню, каждый над своей панелью, с текущими путями."""
    assert inp(fm_page, "Left").input_value() == api.home and inp(fm_page, "Right").input_value() == api.home
    g = fm_page.evaluate("""() => {
        const bar = document.querySelector('.fm-fork-topbar').getBoundingClientRect();
        const tb = document.getElementById('fm-main-top-toolbar').getBoundingClientRect();
        const r = s => document.getElementById('fm-fork-path-' + s).getBoundingClientRect();
        const p = s => FM[s].el.dom.getBoundingClientRect();
        return {bar: [bar.top, bar.height], tb: [tb.top, tb.height], li: [r('Left').left, r('Left').right],
                ri: [r('Right').left, r('Right').right], lp: [p('Left').left, p('Left').right],
                rp: [p('Right').left, p('Right').right]}; }""")
    assert abs(g["bar"][0] - g["tb"][0]) < 2 and abs(g["bar"][1] - g["tb"][1]) < 2
    assert g["lp"][0] <= g["li"][0] and g["li"][1] <= g["lp"][1]
    assert g["rp"][0] <= g["ri"][0] and g["ri"][1] <= g["rp"][1]


def test_top_input_enter_windows_style(fm_page, api, work):
    api.mkdir(work + "/a b")
    i = inp(fm_page, "Right")
    i.fill((work + "/a b").replace("/", "\\") + "\\")
    i.press("Enter")
    wait_input(fm_page, work + "/a b", "Right")
    fm_page.wait_for_function("p => FM.Right.session.path === p", arg=work + "/a b")
    # крошки правой панели тоже обновились (оригинальные)
    assert fm_page.evaluate("FM.Right.down('file-list-path-bar').el.dom.innerText").endswith("a b")


def test_top_input_relative_escape_native_selection(fm_page, api):
    i = inp(fm_page)
    i.fill("site")
    i.press("Enter")
    wait_input(fm_page, api.home + "/site")
    i.fill("/nonexistent")
    i.press("Escape")
    assert i.input_value() == api.home + "/site"
    i.click()
    fm_page.keyboard.press("End")
    fm_page.keyboard.press("Shift+Home")
    assert fm_page.evaluate("(() => { const e = document.activeElement; "
                            "return e.value.substring(e.selectionStart, e.selectionEnd); })()") == api.home + "/site"


def test_top_input_ctrl_l(fm_page, api):
    fm_page.locator(ACTIVE + " .x-grid-item").first.click()
    fm_page.keyboard.press("Control+l")
    fm_page.wait_for_function("document.activeElement.id === 'fm-fork-path-' + FM.Active.toString()", timeout=3000)
    fm_page.keyboard.press("End")
    fm_page.keyboard.press("Backspace")   # не уходит горячей клавише панели («вверх»)
    time.sleep(0.5)
    assert inp(fm_page).input_value() == api.home[:-1]
    fm_page.keyboard.press("Escape")
    assert inp(fm_page).input_value() == api.home


def test_menu_toggle(fm_page):
    """▾ выдвигает оригинальное меню под инпуты (кнопки меню кликабельны), повторно — задвигает."""
    tb = "document.getElementById('fm-main-top-toolbar')"
    top0 = fm_page.evaluate(tb + ".getBoundingClientRect().top")
    fm_page.locator(".fm-fork-menu-toggle").click()
    h = fm_page.evaluate(tb + ".offsetHeight")
    assert abs(fm_page.evaluate(tb + ".getBoundingClientRect().top") - (top0 + h)) < 2
    # кнопка «Файл» оригинального меню видна и открывает меню
    fm_page.locator("#fm-main-top-toolbar .x-btn").first.click()
    fm_page.wait_for_selector(".x-menu:visible", timeout=5000)
    fm_page.keyboard.press("Escape")
    fm_page.locator(".fm-fork-menu-toggle").click()
    assert abs(fm_page.evaluate(tb + ".getBoundingClientRect().top") - top0) < 2


def test_full_path_button(fm_page, api):
    """«Весь путь»: путь выделенного файла сразу в буфере; во всплывающем поле НИЧЕГО не выделено."""
    fm_page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    fm_page.locator(ACTIVE + " .x-grid-item td:first-child", has_text="site").first.click()
    s = side(fm_page)
    fm_page.locator(".fm-fork-path-group[data-side=%s] .fm-fullpath-btn" % s).click()
    field = fm_page.locator(".fm-fullpath-popup input.fm-fullpath-input")
    field.wait_for(timeout=5000)
    assert field.input_value() == api.home + "/site"
    fm_page.wait_for_selector(".fm-fullpath-popup .fm-fullpath-note:not(:empty)", timeout=5000)
    assert fm_page.evaluate("navigator.clipboard.readText()") == api.home + "/site"
    assert not fm_page.evaluate("document.activeElement.classList.contains('fm-fullpath-input')")
    assert fm_page.evaluate("(() => { const f = document.querySelector('.fm-fullpath-input'); "
                            "return f.selectionEnd - f.selectionStart; })()") == 0
    fm_page.keyboard.press("Escape")
    assert fm_page.locator(".fm-fullpath-popup").count() == 0


def test_path_helpers_sftp_and_windows(fm_page):
    """Чистые функции разбора пути: SFTP (путь от домашнего каталога) и Windows-пути."""
    r = fm_page.evaluate("""() => {
        const s = {type: FM.Session.SFTP, path: 'www/site'};
        const root = {type: FM.Session.SFTP, path: '.'};
        const home = {type: FM.Session.HOME, path: '/home/u/www'};
        return {
          sftpDisp: FMFork.displayPath(s), rootDisp: FMFork.displayPath(root),
          sftpFile: FMFork.displayPath(s, 'www/site/a.txt'),
          sftpIn1: FMFork.parseInputPath('~/www/x/', s), sftpIn2: FMFork.parseInputPath('~', s),
          sftpAbs: FMFork.parseInputPath('/var/www', s),
          homeRel: FMFork.parseInputPath('site', home), homeWin: FMFork.parseInputPath('\\\\a\\\\b', home),
          homeTilde: FMFork.parseInputPath('~/x', home), empty: FMFork.parseInputPath('  ', home)
        }; }""")
    assert r["sftpDisp"] == "~/www/site" and r["rootDisp"] == "~" and r["sftpFile"] == "~/www/site/a.txt"
    assert r["sftpIn1"] == "www/x" and r["sftpIn2"] == "/" and r["sftpAbs"] == "/var/www"
    assert r["homeRel"] == "/home/u/www/site" and r["homeWin"] == "/a/b" and r["homeTilde"] == "/x"
    assert r["empty"] is None


def test_mirror_folder_to_other_panel(fm_page, api):
    """⇢ у инпута левой панели — та же папка открывается в правой (как в Total Commander)."""
    fm_page.evaluate("p => FM.Actions.Open.execute(FM.Left, p)", api.home + "/site")
    fm_page.wait_for_function("p => FM.Left.session.path === p", arg=api.home + "/site", timeout=15000)
    fm_page.locator(".fm-fork-path-group[data-side=Left] .fm-fork-mirror-btn").click()
    fm_page.wait_for_function("p => FM.Right.session.path === p", arg=api.home + "/site", timeout=15000)
    assert inp(fm_page, "Right").input_value() == api.home + "/site"


def test_symlinks_open(fm_page, api, work):
    """Двойной клик по симлинку: ссылка на папку открывает цель, на файл — редактор, битая — ошибка."""
    sandbox = os.path.join(os.path.dirname(__file__), "..", "..", "stand", "sandbox-root")
    host = lambda p: os.path.join(sandbox, p.lstrip("/"))
    api.mkdir(work + "/real")
    api.newfile(work + "/real/note.txt")
    api.write(work + "/real/note.txt", "linked content")
    os.symlink(work + "/real", host(work + "/to_dir"))            # абсолютная цель
    os.symlink("real/note.txt", host(work + "/to_file"))
    os.symlink("/nowhere", host(work + "/broken"))
    fm_page.evaluate("p => FM.Actions.Open.execute(FM.Left, p)", work)
    fm_page.wait_for_function("p => FM.Left.session.path === p && FM.Left.filelist.store.getCount() > 3",
                              arg=work, timeout=15000)
    dbl = "n => { const p = FM.Left, r = p.filelist.store.findRecord('name', n, 0, false, true, true);" \
          " p.filelist.getView().fireEvent('itemdblclick', p.filelist.getView(), r); }"
    fm_page.evaluate(dbl, "to_dir")
    fm_page.wait_for_function("p => FM.Left.session.path === p", arg=work + "/real", timeout=15000)
    fm_page.evaluate("p => FM.Actions.Open.execute(FM.Left, p)", work)
    fm_page.wait_for_function("p => FM.Left.session.path === p && FM.Left.filelist.store.getCount() > 3",
                              arg=work, timeout=15000)
    fm_page.evaluate(dbl, "to_file")
    fm_page.wait_for_function("() => Ext.ComponentQuery.query('editor-window').length > 0", timeout=15000)
    content = fm_page.evaluate("() => Ext.ComponentQuery.query('editor-window')[0].fileContent")
    assert content == "linked content"
    fm_page.evaluate("() => Ext.ComponentQuery.query('editor-window').forEach(w => w.close())")
    fm_page.evaluate(dbl, "broken")
    fm_page.wait_for_function("() => Array.from(document.querySelectorAll('.x-window')).some("
                              "w => w.offsetParent && /nowhere/.test(w.textContent))", timeout=10000)


def test_logout_url(fm_page):
    """«Выход» ведёт на FM_LOGOUT_URL, если он задан (window.FM_LOGOUT_URL из app.html)."""
    assert fm_page.evaluate("window.FM_LOGOUT_URL") == ""
    fm_page.evaluate("window.FM_LOGOUT_URL = location.origin + '/login?language=en&bye=1'")
    fm_page.evaluate("FM.Actions.Logout.execute()")
    fm_page.wait_for_url("**/login?language=en&bye=1", timeout=15000)


def test_editor_size_limit(fm_page):
    assert fm_page.evaluate("FM.File.MAX_SIZE") == 20 * 1024 * 1024


def test_login_page_language(page):
    """Страница входа: выбор флага сразу перерисовывает её на этом языке; без выбора — язык браузера."""
    from fmclient import BASE
    page.goto(BASE + "/login")                      # браузер en-US
    assert page.locator("input[name=language][value=en]").is_checked()
    sign_in = page.locator("#login-submit").inner_text()
    page.locator("input[name=language][value=ru]").check()
    page.wait_for_url("**/login?language=ru", timeout=10000)
    assert page.locator("input[name=language][value=ru]").is_checked()
    assert page.locator("#login-submit").inner_text() != sign_in


# --- загрузка перетаскиванием ---------------------------------------------------------------------

DROP_JS = """([sel, files, type]) => {
    const el = document.querySelector(sel);
    const dt = new DataTransfer();
    files.forEach(([n, c]) => dt.items.add(new File([c], n, {type: 'text/plain'})));
    const r = el.getBoundingClientRect();
    const ev = new DragEvent(type, {dataTransfer: dt, bubbles: true, cancelable: true,
                                    clientX: r.x + 20, clientY: r.y + 20});
    el.dispatchEvent(ev);
    return ev.defaultPrevented; }"""


def test_drop_uploads_to_panel(fm_page, api, work):
    fm_page.evaluate("p => FM.Actions.Open.execute(FM.Right, p)", work)
    fm_page.wait_for_function("p => FM.Right.session.path === p", arg=work, timeout=15000)
    right_view = ".fm-file-list-panel >> nth=1"
    sel = "#" + fm_page.evaluate("FM.Right.filelist.getView().el.dom.id")
    assert fm_page.evaluate(DROP_JS, [sel, [["dnd-1.txt", "one"]], "dragover"]) is True
    assert fm_page.evaluate("FM.Right.el.dom.classList.contains('fm-drop-target')")
    assert fm_page.evaluate(DROP_JS, [sel, [["dnd-1.txt", "one"], ["dnd-2.txt", "два"]], "drop"]) is True
    assert not fm_page.evaluate("FM.Right.el.dom.classList.contains('fm-drop-target')")
    # загрузка уходит в правую панель (она становится активной), окно само закрывается
    fm_page.wait_for_function("() => FM.Active === FM.Right")
    fm_page.wait_for_function("() => FM.Right.filelist.getStore().getRange().filter(r => "
                              "r.get('name').startsWith('dnd-')).length === 2", timeout=20000)
    fm_page.wait_for_function("() => !Ext.ComponentQuery.query('window').some(w => w.hasCls('fm-upload-dialog')"
                              " && w.isVisible())", timeout=10000)
    assert api.read(work + "/dnd-2.txt")["content"] == "два"
    assert right_view  # noqa


def test_drop_outside_panels_is_swallowed(fm_page):
    """Брошенный мимо панелей файл не открывается браузером вместо приложения."""
    assert fm_page.evaluate(DROP_JS, ["#fm-main-buttons-toolbar", [["x.txt", "x"]], "drop"]) is True
    time.sleep(0.5)
    assert fm_page.evaluate("Ext.ComponentQuery.query('window').filter(w => w.hasCls('fm-upload-dialog')"
                            " && w.isVisible()).length") == 0


def wait_upload_done(page):
    """Окно загрузки сначала появляется (после создания папок), потом закрывается само."""
    page.wait_for_function("() => Ext.ComponentQuery.query('window').some(w => w.hasCls('fm-upload-dialog'))",
                           timeout=30000)
    page.wait_for_function("() => !Ext.ComponentQuery.query('window').some(w => w.hasCls('fm-upload-dialog')"
                           " && !w.isDestroyed && w.isVisible())", timeout=30000)


def test_drop_folder_tree(fm_page, api, work):
    """Папки перетаскиванием: структура сохраняется (вложенные и пустые папки, файлы — каждый в своей)."""
    fm_page.evaluate("p => FM.Actions.Open.execute(FM.Active, p)", work)
    fm_page.wait_for_function("p => FM.Active.session.path === p", arg=work, timeout=15000)
    fm_page.evaluate("""() => { FMFork.uploadTree(FM.Active, ['proj', 'proj/src', 'proj/src/deep', 'proj/empty'], [
        {dir: '', file: new File(['root'], 'top.txt')},
        {dir: 'proj', file: new File(['readme'], 'README.md')},
        {dir: 'proj/src', file: new File(['main'], 'main.py')},
        {dir: 'proj/src/deep', file: new File(['x'], 'x.txt')}]); }""")
    wait_upload_done(fm_page)
    names = lambda p: sorted(n for n in api.ls(p) if n != "..")
    assert {"proj", "top.txt"} <= set(names(work))
    assert set(names(work + "/proj")) >= {"README.md", "src", "empty"}
    assert set(names(work + "/proj/src")) >= {"main.py", "deep"}
    assert api.read(work + "/proj/src/deep/x.txt")["content"] == "x"
    assert names(work + "/proj/empty") == []
    # повторно в ту же папку: спрашивает про перезапись, «Да» — файлы обновляются
    fm_page.evaluate("p => FM.Actions.Open.execute(FM.Active, p)", work)
    fm_page.wait_for_timeout(1000)
    fm_page.evaluate("""() => { FMFork.uploadTree(FM.Active, ['proj'], [{dir: 'proj', file: new File(['v2'], 'README.md')}]); }""")
    fm_page.locator(".x-window .x-btn", has_text="Yes").first.click()
    wait_upload_done(fm_page)
    assert api.read(work + "/proj/README.md")["content"] == "v2"


def test_collect_dropped_entries(fm_page):
    """Обход перетащенных папок (FileSystemEntry): вложенность, пустые папки, чтение содержимого порциями."""
    r = fm_page.evaluate("""async () => {
        const file = (name) => ({isFile: true, isDirectory: false, name, file: (ok) => ok(new File([name], name))});
        const dir = (name, children, chunk) => ({isFile: false, isDirectory: true, name, createReader() {
            let pos = 0;   // как в Chrome: readEntries отдаёт порции, последняя — пустая
            return {readEntries(ok) { const part = children.slice(pos, pos + chunk); pos += chunk; ok(part); }};
        }});
        const many = Array.from({length: 7}, (_, i) => file('f' + i + '.txt'));
        const tree = await FMFork.collectEntries([
            file('top.txt'),
            dir('site', [file('index.php'), dir('css', [file('a.css')], 10), dir('empty', [], 10), dir('big', many, 3)], 2)]);
        return {dirs: tree.dirs, files: tree.files.map(f => (f.dir ? f.dir + '/' : '') + f.file.name)};
    }""")
    assert r["dirs"] == ["site", "site/css", "site/empty", "site/big"]
    assert r["files"][:3] == ["top.txt", "site/index.php", "site/css/a.css"]
    assert sorted(f for f in r["files"] if f.startswith("site/big/")) == ["site/big/f%d.txt" % i for i in range(7)]


# --- retina ---------------------------------------------------------------------------------------

def test_retina_icons(browser, creds):
    ctx = browser.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 900},
                              device_scale_factor=2, locale="en-US")
    p = ctx.new_page()
    login(p, creds)
    bg = """s => { const d = document.querySelector(s); const c = getComputedStyle(d);
        return [c.backgroundImage, c.backgroundSize]; }"""
    # иконки типов файлов — всегда оригинальный спрайт (крупных версий того же рисунка нет)
    assert "icons_16.png" in p.evaluate(bg, ".fm-file-list-panel .cell-icon > div")[0]
    # иконка действия с 32-px версией того же рисунка — чёткая по умолчанию, без галочки
    assert not p.evaluate("document.documentElement.classList.contains('fm-retina-max')")
    home = p.evaluate(bg, ".fm-file-list-panel .fm-action-home")
    assert "actions/32/home.png" in home[0] and home[1] == "16px 16px"
    # «Удалённый сервер» у 32-px версии другой рисунок — остаётся оригинальной
    p.evaluate("""() => { const e = document.createElement('span'); e.className = 'fm-action-remote';
        e.id = 'probe-remote'; document.body.appendChild(e); }""")
    assert "actions/16/remote.png" in p.evaluate(bg, "#probe-remote")[0]
    # большие кнопки главной панели не сжимаются
    assert p.evaluate(bg, "#fm-main-buttons-toolbar .fm-action-upload")[1] == "auto"
    # Настройки → Интерфейс → «Режим max retina» (свои иконки из fm-retina-max.css) → Сохранить
    p.evaluate("FM.Actions.Settings.execute()")
    win = p.locator(".fm-settings-window")
    win.wait_for(timeout=10000)
    win.locator(".x-tab", has_text="Interface").click()
    win.locator(".x-form-cb-label", has_text="Max retina mode").click()
    win.locator(".x-btn", has_text="Save").click()
    p.wait_for_function("document.documentElement.classList.contains('fm-retina-max')", timeout=5000)
    # тест увеличенных иконок: по умолчанию вариант xBRZ
    if os.path.exists(os.path.join(os.path.dirname(__file__), "..", "..", "sprutio", "app", "public", "fm",
                                   "resources", "images", "retina-max", "xbrz", "icons_16@2x.png")):
        assert "retina-max/xbrz/icons_16@2x.png" in p.evaluate(bg, ".fm-file-list-panel .cell-icon > div")[0]
        assert "retina-max/xbrz/actions/remote.png" in p.evaluate(bg, "#probe-remote")[0]
        # родные 32-px того же рисунка не подменяются
        assert "actions/32/home.png" in p.evaluate(bg, ".fm-file-list-panel .fm-action-home")[0]
    # настройка переживает перезагрузку
    p.reload()
    p.wait_for_selector(".fm-file-list-panel .x-grid-item", timeout=45000)
    p.wait_for_function("document.documentElement.classList.contains('fm-retina-max')", timeout=10000)
    # переключение варианта на Real-ESRGAN
    p.evaluate("FM.Actions.Settings.execute()")
    win = p.locator(".fm-settings-window")
    win.wait_for(timeout=10000)
    win.locator(".x-tab", has_text="Interface").click()
    win.locator(".x-form-cb-label", has_text="Real-ESRGAN").click()
    win.locator(".x-btn", has_text="Save").click()
    p.wait_for_function("document.documentElement.classList.contains('fm-rv-esrgan')", timeout=5000)
    assert not p.evaluate("document.documentElement.classList.contains('fm-rv-xbrz')")
    assert "retina-max/esrgan/" in p.evaluate(bg, ".fm-file-list-panel .cell-icon > div")[0]
    os.makedirs(SHOTS, exist_ok=True)
    p.locator(".fm-file-list-panel").first.screenshot(path=os.path.join(SHOTS, "panel-dpr2-retina.png"))
    ctx.close()
