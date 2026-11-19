/*
 * Дополнения форка sprutio к интерфейсу (без пересборки Sencha Cmd).
 * Подключается из app.html после загрузчика приложения и в production-, и в dev-режиме.
 * Классы приложения появляются асинхронно, поэтому дополнения применяются, когда класс уже определён.
 */
(function () {
    // без 'use strict': callParent в ExtJS 5 опирается на function.caller, который в strict-режиме недоступен

    var STORAGE_KEY = 'fm-fork-fast-search';

    function storedFast() {
        try {
            // по умолчанию включён; выключен, только если пользователь сам снял галочку
            return window.localStorage.getItem(STORAGE_KEY) !== '0';
        } catch (e) {
            return true;
        }
    }

    function storeFast(value) {
        try {
            window.localStorage.setItem(STORAGE_KEY, value ? '1' : '0');
        } catch (e) { /* localStorage недоступен — просто не запоминаем */ }
    }

    function tr(text) {
        if (typeof window.t === 'function') {
            return window.t.apply(window, arguments);
        }
        var args = arguments;
        return String(text).replace(/\$(\d+)/g, function (m, n) { return args[n] !== undefined ? args[n] : m; });
    }

    function whenDefined(className, apply) {
        var tries = 0;
        (function poll() {
            var cls = window.Ext && Ext.ClassManager && Ext.ClassManager.get(className);
            if (cls) {
                apply(cls);
            } else if (tries++ < 600) {
                setTimeout(poll, 100);
            } else if (window.console) {
                console.warn('fm-fork: class not found', className);
            }
        })();
    }

    // --- Быстрый поиск (эксперимент): галочка в формах поиска ---------------------------------------
    function addFastCheckbox(cls) {
        var proto = cls.prototype;
        if (proto.__fmForkFast) {
            return;
        }
        var originalInit = proto.initComponent;
        proto.__fmForkFast = true;
        proto.initComponent = function () {
                originalInit.apply(this, arguments);
                this.add({
                    xtype: 'checkbox',
                    name: 'search-fast',
                    boxLabel: tr('Fast search'),
                    checked: storedFast(),
                    listeners: {
                        change: function (cb, value) {
                            storeFast(value);
                        }
                    }
                });
        };
    }

    whenDefined('FM.view.forms.SearchTextForm', addFastCheckbox);
    whenDefined('FM.view.forms.SearchFileForm', addFastCheckbox);

    // --- передать params.fast при запуске поиска -------------------------------------------------------
    function patchProcess(actionName) {
        var tries = 0;
        (function poll() {
            var action = window.FM && FM.Actions && FM.Actions[actionName];
            if (!action || typeof action.process !== 'function') {
                if (tries++ < 600) {
                    setTimeout(poll, 100);
                }
                return;
            }
            if (action.__fmForkFast) {
                return;
            }
            var original = action.process;
            action.process = function (button, searchWindow, session, params, filesList, status) {
                // первый вызов (status ещё нет) — запуск поиска; дальше process опрашивает статус
                if (!status && params && searchWindow) {
                    var cb = Ext.ComponentQuery.query('checkbox[name=search-fast]', searchWindow)[0];
                    if (cb && cb.getValue()) {
                        params = Ext.apply({}, params, {fast: true});
                    }
                }
                return original.call(this, button, searchWindow, session, params, filesList, status);
            };
            action.__fmForkFast = true;
        })();
    }

    patchProcess('SearchText');
    patchProcess('SearchFiles');

    // =================================================================================================
    // «Режим max retina»: свои иконки из fm-retina-max.css по галочке (базовая retina — fm-retina.css, всегда)
    // =================================================================================================

    var RETINA_KEY = 'fm-fork-retina-max';

    function storedRetina() {
        try {
            return window.localStorage.getItem(RETINA_KEY) === '1';
        } catch (e) {
            return false;
        }
    }

    var RETINA_VARIANT_KEY = 'fm-fork-retina-variant';
    var RETINA_VARIANTS = ['xbrz', 'esrgan'];   // тест увеличенных иконок (css/fm-retina-test.css)

    function storedVariant() {
        try {
            var v = window.localStorage.getItem(RETINA_VARIANT_KEY);
            return RETINA_VARIANTS.indexOf(v) !== -1 ? v : RETINA_VARIANTS[0];
        } catch (e) {
            return RETINA_VARIANTS[0];
        }
    }

    function applyRetina(on, variant) {
        var root = document.documentElement;
        root.classList.toggle('fm-retina-max', !!on);
        variant = variant || storedVariant();
        RETINA_VARIANTS.forEach(function (v) {
            root.classList.toggle('fm-rv-' + v, v === variant);
        });
    }

    applyRetina(storedRetina());

    whenDefined('FM.view.forms.SettingsForm', function (cls) {
        var proto = cls.prototype;
        if (proto.__fmForkRetina) {
            return;
        }
        proto.__fmForkRetina = true;
        var originalInit = proto.initComponent;
        proto.initComponent = function () {
            originalInit.apply(this, arguments);
            var tabs = this.down('tabpanel');
            if (!tabs) {
                return;
            }
            tabs.add({
                title: tr('Interface'),
                bodyPadding: 10,
                border: false,
                items: [{
                    xtype: 'checkbox',
                    name: 'fm_fork_retina_max',
                    boxLabel: tr('Max retina mode'),
                    checked: storedRetina()
                }, {
                    xtype: 'radiogroup',
                    fieldLabel: tr('Upscaled icons (test)'),
                    labelWidth: 170,
                    margin: '6 0 0 22',
                    columns: 1,
                    items: [
                        {boxLabel: 'xBRZ', name: 'fm_fork_retina_variant', inputValue: 'xbrz',
                         checked: storedVariant() === 'xbrz'},
                        {boxLabel: 'Real-ESRGAN', name: 'fm_fork_retina_variant', inputValue: 'esrgan',
                         checked: storedVariant() === 'esrgan'}
                    ]
                }, {
                    xtype: 'component',
                    cls: 'fm-settings-hint',
                    html: tr('Upscaled original icons on Retina/4K screens (test: compare the two methods). Without it the original icons are shown, sharp where a native large version exists.')
                }]
            });
        };
    });

    whenDefined('FM.view.windows.SettingsWindow', function (cls) {
        var proto = cls.prototype;
        if (proto.__fmForkRetina) {
            return;
        }
        proto.__fmForkRetina = true;
        var originalInit = proto.initComponent;
        proto.initComponent = function () {
            originalInit.apply(this, arguments);
            var win = this;
            win.on('beforeshow', function () {
                var cb = Ext.ComponentQuery.query('checkbox[name=fm_fork_retina_max]', win)[0];
                if (cb) {
                    cb.setValue(storedRetina());
                }
                var radio = Ext.ComponentQuery.query('radio[name=fm_fork_retina_variant][inputValue=' + storedVariant() + ']', win)[0];
                if (radio) {
                    radio.setValue(true);
                }
            });
            if (win.save_btn) {
                // настройка браузерная (зависит от экрана), на сервер не уходит — применяем по «Сохранить»
                win.save_btn.on('click', function () {
                    var cb = Ext.ComponentQuery.query('checkbox[name=fm_fork_retina_max]', win)[0];
                    if (!cb) {
                        return;
                    }
                    var radio = Ext.ComponentQuery.query('radio[name=fm_fork_retina_variant]', win)[0];
                    var variant = radio ? radio.getGroupValue() : storedVariant();
                    try {
                        window.localStorage.setItem(RETINA_KEY, cb.getValue() ? '1' : '0');
                        window.localStorage.setItem(RETINA_VARIANT_KEY, variant);
                    } catch (e) { /* без localStorage — только до перезагрузки */ }
                    applyRetina(cb.getValue(), variant);
                });
            }
        };
    });

    // =================================================================================================
    // Строка пути: оригинальные хлебные крошки на панелях не трогаем. Поверх верхней чёрной полосы
    // (главное меню) — своя полоса с двумя обычными инпутами, каждый над своей панелью (как букмарклет
    // extra_sprut_io). Кнопка ▾ временно выдвигает оригинальное меню вниз, под инпуты.
    // Кнопка «Весь путь» — полный путь выделенного файла: сразу в буфер обмена и во всплывающее поле.
    // =================================================================================================

    function isSftp(session) {
        return !!(session && window.FM && FM.Session && session.type === FM.Session.SFTP);
    }

    function isWindowsPath(path) {
        return path.indexOf('\\') !== -1 || /^[a-zA-Z]:$/.test(path);
    }

    // путь для показа: SFTP хранит путь относительно домашнего каталога ('.', 'www/x') → '~', '~/www/x'
    function displayPath(session, path) {
        path = path || (session && session.path) || '/';
        if (isSftp(session) && path.charAt(0) !== '/') {
            path = path.replace(/^\.\/?/, '');
            return path === '' ? '~' : '~/' + path;
        }
        return path;
    }

    // введённый текст → путь для FM.Actions.Open
    function parseInputPath(text, session) {
        var path = String(text).trim().replace(/^["']|["']$/g, '');
        if (path === '') {
            return null;
        }
        var current = (session && session.path) || '/';
        if (!isWindowsPath(current)) {
            path = path.replace(/\\/g, '/');       // путь в стиле Windows: \www\site → /www/site
            path = path.replace(/\/{2,}/g, '/');
            if (path.length > 1) {
                path = path.replace(/\/$/, '');
            }
        }
        if (isSftp(session)) {
            if (path === '~') {
                return '/';
            }
            if (path.indexOf('~/') === 0) {
                return path.substring(2) || '/';
            }
            return path;
        }
        if (path.charAt(0) === '~') {
            path = '/' + path.replace(/^~\/?/, '');
        }
        if (!isWindowsPath(current) && path.charAt(0) !== '/') {
            path = (current === '/' ? '' : current) + '/' + path;   // относительный — от текущей папки
        }
        return path;
    }

    function panelBySide(side) {
        return window.FM ? FM[side] : null;
    }

    function getPathInput(panel) {
        return panel ? document.getElementById('fm-fork-path-' + panel.toString()) : null;
    }

    function focusGrid(panel) {
        if (panel && panel.filelist && panel.filelist.getView) {
            panel.filelist.getView().focus();
        }
    }

    // --- «Весь путь» -----------------------------------------------------------------------------------
    var fullPathPopup = null;

    function closeFullPath() {
        if (fullPathPopup) {
            if (fullPathPopup.parentNode) {
                fullPathPopup.parentNode.removeChild(fullPathPopup);
            }
            fullPathPopup = null;
        }
    }

    function copyText(text) {
        function legacy() {
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0';
            document.body.appendChild(ta);
            ta.select();
            var ok = false;
            try {
                ok = document.execCommand('copy');
            } catch (e) { /* нет — подскажем Ctrl+C */ }
            document.body.removeChild(ta);
            return ok;
        }
        if (navigator.clipboard && window.isSecureContext) {
            return navigator.clipboard.writeText(text).then(function () { return true; }, legacy);
        }
        return Promise.resolve(legacy());
    }

    function selectedFullPath(panel) {
        var record = FM.helpers.GetLastSelected ? FM.helpers.GetLastSelected(panel) : null;
        if (record && record.get && record.get('name') && record.get('name') !== '..') {
            return displayPath(panel.session, FM.helpers.GetAbsName(panel.session, record));
        }
        return displayPath(panel.session);
    }

    function showFullPath(panel) {
        closeFullPath();
        var anchor = getPathInput(panel);
        if (!anchor) {
            return;
        }
        var text = selectedFullPath(panel);
        var box = document.createElement('div');
        box.className = 'fm-fullpath-popup';
        box.innerHTML = '<input type="text" readonly class="fm-fullpath-input" spellcheck="false">' +
            '<span class="fm-fullpath-note"></span>';
        var field = box.firstChild;
        var note = box.lastChild;
        field.value = text;
        var r = anchor.getBoundingClientRect();
        box.style.left = Math.round(r.left) + 'px';
        box.style.top = Math.round(r.bottom + 4) + 'px';
        box.style.width = Math.max(Math.round(r.width), 320) + 'px';
        document.body.appendChild(box);
        fullPathPopup = box;
        ['keydown', 'keyup', 'keypress'].forEach(function (type) {
            field.addEventListener(type, function (e) { e.stopPropagation(); });
        });
        // путь уже в буфере; ничего не выделяем — нужную часть выделяют мышью сами
        copyText(text).then(function (ok) {
            note.textContent = ok ? tr('Copied to clipboard') : tr('Select and press Ctrl+C to copy');
        });
    }

    document.addEventListener('mousedown', function (e) {
        if (fullPathPopup && !fullPathPopup.contains(e.target) &&
            !(e.target.closest && e.target.closest('.fm-fullpath-btn'))) {
            closeFullPath();
        }
    }, true);

    // --- верхняя полоса с инпутами ---------------------------------------------------------------------
    var topbar = null;
    var topToolbarEl = null;

    function setExpanded(on) {
        if (!topbar || !topToolbarEl) {
            return;
        }
        topbar.classList.toggle('fm-fork-topbar-expanded', !!on);
        topToolbarEl.classList.toggle('fm-fork-menu-expanded', !!on);
        // оригинальное меню выезжает вниз, под нашу полосу (поверх контента, без перекладки ExtJS)
        topToolbarEl.style.transform = on ? 'translateY(' + topToolbarEl.offsetHeight + 'px)' : '';
        var t = topbar.querySelector('.fm-fork-menu-toggle');
        if (t) {
            t.title = on ? tr('Hide the menu') : tr('Show the menu');
        }
    }

    function positionTopbar() {
        if (!topbar || !topToolbarEl) {
            return;
        }
        var tr_ = topToolbarEl.getBoundingClientRect();
        var shift = topToolbarEl.classList.contains('fm-fork-menu-expanded') ? topToolbarEl.offsetHeight : 0;
        topbar.style.left = Math.round(tr_.left) + 'px';
        topbar.style.top = Math.round(tr_.top - shift) + 'px';
        topbar.style.width = Math.round(tr_.width) + 'px';
        topbar.style.height = Math.round(topToolbarEl.offsetHeight) + 'px';
        ['Left', 'Right'].forEach(function (side) {
            var panel = panelBySide(side);
            var group = topbar.querySelector('.fm-fork-path-group[data-side="' + side + '"]');
            if (!group || !panel || !panel.el) {
                return;
            }
            var pr = panel.el.dom.getBoundingClientRect();
            group.style.left = Math.round(pr.left - tr_.left + 4) + 'px';
            group.style.width = Math.max(Math.round(pr.width - 8), 120) + 'px';
        });
    }

    function syncTopInputs() {
        ['Left', 'Right'].forEach(function (side) {
            var panel = panelBySide(side);
            var input = getPathInput(panel);
            if (input && panel.session && document.activeElement !== input) {
                input.value = displayPath(panel.session);
            }
            if (input) {
                input.classList.toggle('fm-path-input-active', FM.Active === panel);
            }
        });
    }

    function buildTopbar() {
        if (topbar) {
            return true;
        }
        topToolbarEl = document.getElementById('fm-main-top-toolbar');
        if (!topToolbarEl || !panelBySide('Left') || !panelBySide('Right') || !FM.Left.el || !FM.Right.el) {
            return false;
        }
        topbar = document.createElement('div');
        topbar.className = 'fm-fork-topbar';
        ['Left', 'Right'].forEach(function (side) {
            var group = document.createElement('div');
            group.className = 'fm-fork-path-group';
            group.setAttribute('data-side', side);
            group.innerHTML = '<input type="text" class="fm-path-input" spellcheck="false" autocomplete="off" id="fm-fork-path-' +
                side + '"><span class="fm-fullpath-btn" role="button"></span>' +
                (side === 'Right' ? '<span class="fm-fork-menu-toggle" role="button">▾</span>' : '');
            topbar.appendChild(group);
            var input = group.querySelector('input');
            var btn = group.querySelector('.fm-fullpath-btn');
            btn.title = tr('Full path of the selected file (copied to clipboard)');
            input.addEventListener('focus', function () {
                var panel = panelBySide(side);
                if (FM.Active !== panel && FM.helpers && FM.helpers.SetActivePanel) {
                    FM.helpers.SetActivePanel(panel);
                    setTimeout(function () { input.focus(); }, 0);   // SetActivePanel отдаёт фокус гриду
                }
            });
            input.addEventListener('keydown', function (e) {
                e.stopPropagation();   // не отдавать клавиши горячим клавишам панелей (Backspace, Delete, Tab…)
                var panel = panelBySide(side);
                if (e.key === 'Enter') {
                    e.preventDefault();
                    var path = parseInputPath(input.value, panel.session);
                    if (path !== null && path !== panel.session.path) {
                        FM.Actions.Open.execute(panel, path);
                    } else {
                        input.value = displayPath(panel.session);
                    }
                    focusGrid(panel);
                } else if (e.key === 'Escape') {
                    e.preventDefault();
                    input.value = displayPath(panel.session);
                    focusGrid(panel);
                }
            });
            ['keyup', 'keypress'].forEach(function (type) {
                input.addEventListener(type, function (e) { e.stopPropagation(); });
            });
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                showFullPath(panelBySide(side));
            });
        });
        var toggle = topbar.querySelector('.fm-fork-menu-toggle');
        toggle.title = tr('Show the menu');
        toggle.addEventListener('click', function (e) {
            e.preventDefault();
            setExpanded(!topToolbarEl.classList.contains('fm-fork-menu-expanded'));
        });
        document.body.appendChild(topbar);
        positionTopbar();
        syncTopInputs();
        window.addEventListener('resize', function () {
            setTimeout(positionTopbar, 50);
        });
        if (window.ResizeObserver) {
            var ro = new ResizeObserver(function () { positionTopbar(); });
            ro.observe(topToolbarEl);
            ro.observe(FM.Left.el.dom);
            ro.observe(FM.Right.el.dom);
        }
        return true;
    }

    whenDefined('FM.view.panels.FileListPanel', function (cls) {
        var proto = cls.prototype;
        if (proto.__fmForkPathBar) {
            return;
        }
        proto.__fmForkPathBar = true;
        var original = proto.updatePathBar;
        proto.updatePathBar = function () {
            var result = original.apply(this, arguments);   // оригинальные хлебные крошки
            if (buildTopbar()) {
                syncTopInputs();
                positionTopbar();
            }
            return result;
        };
    });

    // активная панель меняется — подсветить её инпут
    (function waitHelpers() {
        if (!(window.FM && FM.helpers && FM.helpers.SetActivePanel)) {
            setTimeout(waitHelpers, 200);
            return;
        }
        var originalSet = FM.helpers.SetActivePanel;
        FM.helpers.SetActivePanel = function () {
            var r = originalSet.apply(this, arguments);
            syncTopInputs();
            return r;
        };
    })();

    function editingElement(el) {
        if (!el) {
            return false;
        }
        var tag = (el.tagName || '').toLowerCase();
        return tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable ||
            !!(el.closest && el.closest('.ace_editor'));
    }

    function modalOpen() {
        var top = Ext.WindowManager && Ext.WindowManager.getActive && Ext.WindowManager.getActive();
        return !!(top && top.isVisible && top.isVisible() && top.modal);
    }

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeFullPath();
        }
        // Ctrl+L / Alt+D (как в Проводнике и браузерах) — фокус в инпут пути активной панели
        var key = (e.key || '').toLowerCase();
        var hit = (e.ctrlKey && !e.altKey && !e.shiftKey && (key === 'l' || key === 'д')) ||
            (e.altKey && !e.ctrlKey && !e.shiftKey && (key === 'd' || key === 'в'));
        if (!hit || !window.FM || !FM.Active || editingElement(document.activeElement) || modalOpen()) {
            return;
        }
        var input = getPathInput(FM.Active);
        if (!input) {
            return;
        }
        e.preventDefault();
        e.stopPropagation();
        input.focus();
        input.select();
    }, true);

    // =================================================================================================
    // Загрузка перетаскиванием: файлы с компьютера бросаются на панель → загрузка в её текущую папку
    // =================================================================================================

    function hasFiles(e) {
        var types = e.dataTransfer && e.dataTransfer.types;
        if (!types) {
            return false;
        }
        for (var i = 0; i < types.length; i++) {
            if (types[i] === 'Files') {
                return true;
            }
        }
        return false;
    }

    function panelFromTarget(target) {
        if (!window.FM) {
            return null;
        }
        var panels = [FM.Left, FM.Right];
        for (var i = 0; i < panels.length; i++) {
            var p = panels[i];
            if (p && p.el && p.el.dom && p.el.dom.contains(target)) {
                return p;
            }
        }
        return null;
    }

    function canUpload(panel) {
        try {
            return !!(panel && panel.session && FM.helpers.isAllowed(FM.Actions.Upload, panel, []));
        } catch (err) {
            return false;
        }
    }

    var highlighted = null;
    function highlight(panel, allowed) {
        if (highlighted && highlighted !== panel) {
            highlighted.removeCls(['fm-drop-target', 'fm-drop-denied']);
        }
        highlighted = panel;
        if (panel) {
            panel.el.dom.setAttribute('data-fm-drop-label',
                allowed ? tr('Drop files to upload') + '\n' + displayPath(panel.session) : tr('Upload is not available here'));
            panel.addCls(allowed ? 'fm-drop-target' : 'fm-drop-denied');
            panel.removeCls(allowed ? 'fm-drop-denied' : 'fm-drop-target');
        }
    }

    var dragDepth = 0;
    document.addEventListener('dragenter', function (e) {
        if (hasFiles(e)) {
            dragDepth++;
        }
    }, false);
    document.addEventListener('dragleave', function (e) {
        if (hasFiles(e) && --dragDepth <= 0) {
            dragDepth = 0;
            highlight(null);
        }
    }, false);
    document.addEventListener('dragover', function (e) {
        if (!hasFiles(e)) {
            return;
        }
        e.preventDefault();  // иначе браузер откроет файл вместо приложения
        var panel = panelFromTarget(e.target);
        var allowed = !!panel && !modalOpen() && canUpload(panel);
        e.dataTransfer.dropEffect = allowed ? 'copy' : 'none';
        highlight(panel, allowed);
    }, false);
    document.addEventListener('drop', function (e) {
        if (!hasFiles(e)) {
            return;
        }
        e.preventDefault();
        dragDepth = 0;
        var panel = panelFromTarget(e.target);
        highlight(null);
        if (!panel || modalOpen() || !canUpload(panel)) {
            return;
        }
        // DataTransfer живёт только внутри обработчика — разбираем сразу
        var files = [];
        var skipped = [];
        var items = e.dataTransfer.items;
        var i;
        if (items && items.length) {
            for (i = 0; i < items.length; i++) {
                if (items[i].kind !== 'file') {
                    continue;
                }
                var entry = items[i].webkitGetAsEntry ? items[i].webkitGetAsEntry() : null;
                if (entry && entry.isDirectory) {
                    skipped.push(entry.name);
                    continue;
                }
                var f = items[i].getAsFile();
                if (f) {
                    files.push(f);
                }
            }
        } else {
            for (i = 0; i < e.dataTransfer.files.length; i++) {
                files.push(e.dataTransfer.files[i]);
            }
        }
        uploadDropped(panel, files, skipped);
    }, false);

    function uploadDropped(panel, files, skipped) {
        if (skipped.length) {
            FM.helpers.ShowWarning(tr('Folders cannot be uploaded by drag and drop yet, skipped: $1', skipped.join(', ')));
        }
        if (!files.length) {
            return;
        }
        if (FM.Active !== panel) {
            FM.helpers.SetActivePanel(panel);
        }
        var before = Ext.ComponentQuery.query('window').filter(function (w) {
            return w.hasCls && w.hasCls('fm-upload-dialog');
        });
        FM.Actions.Upload.execute();
        var dialog = Ext.ComponentQuery.query('window').filter(function (w) {
            return w.hasCls && w.hasCls('fm-upload-dialog') && before.indexOf(w) === -1;
        }).pop();
        if (!dialog || !dialog.queue) {
            return;
        }
        dialog.queue.clearUploadedItems();
        dialog.queue.addFiles(files);
        // всё прошло без ошибок — окно закрывается само, как в Проводнике
        dialog.on('uploadcomplete', function (dlg, manager, uploaded, errorCount) {
            if (!errorCount) {
                setTimeout(function () {
                    if (!dlg.isDestroyed) {
                        dlg.close();
                    }
                }, 800);
            }
        });
        dialog.onInitUpload();
    }

    // для тестов и отладки
    window.FMFork = {
        displayPath: displayPath,
        parseInputPath: parseInputPath,
        selectedFullPath: selectedFullPath,
        showFullPath: showFullPath,
        setMenuExpanded: setExpanded,
        uploadDropped: uploadDropped
    };
})();
