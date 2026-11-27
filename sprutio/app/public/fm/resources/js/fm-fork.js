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
    // «Редактор+»: новый Ace (1.45) по галочке — по умолчанию родной Ace 1.2.0. Версия выбирается в app.html
    // при загрузке страницы, поэтому переключение — после перезагрузки. Проверка кода и ИИ-подсказки
    // работают только в новом редакторе (fm-ace-next.js).
    // =================================================================================================

    var ACE_NEXT_KEY = 'fm-fork-ace-next';
    var ACE_LINT_KEY = 'fm-fork-ace-lint';
    var AI_KEY = 'fm-fork-ai';
    var AI_DEFAULTS = {provider: 'off', auto: true, delay: 600,
                       ollamaUrl: 'http://localhost:11434', ollamaModel: 'qwen2.5-coder:1.5b'};

    function lsGet(key) {
        try { return window.localStorage.getItem(key); } catch (e) { return null; }
    }

    function lsSet(key, value) {
        try { window.localStorage.setItem(key, value); } catch (e) { /* только до перезагрузки */ }
    }

    function storedAceNext() { return lsGet(ACE_NEXT_KEY) === '1'; }

    function storedLint() { return lsGet(ACE_LINT_KEY) !== '0'; }

    function storedAi() {
        var out = {}, k, saved = {};
        try { saved = JSON.parse(lsGet(AI_KEY) || '{}') || {}; } catch (e) { saved = {}; }
        for (k in AI_DEFAULTS) {
            if (AI_DEFAULTS.hasOwnProperty(k)) {
                out[k] = saved.hasOwnProperty(k) ? saved[k] : AI_DEFAULTS[k];
            }
        }
        return out;
    }

    function aiServerStatus(cmp) {
        if (!cmp) {
            return;
        }
        cmp.update(tr('Server: checking…'));
        $.ajax('/fork/ai/status', {
            dataType: 'json',
            success: function (data) {
                if (cmp.isDestroyed) { return; }
                cmp.update(data && data.enabled
                    ? tr('Server: $1 ($2)', Ext.String.htmlEncode(data.model || '?'), Ext.String.htmlEncode(data.api || ''))
                    : tr('Server: not configured (FM_AI_BASE_URL, FM_AI_MODEL in the app environment)'));
            },
            error: function () {
                if (!cmp.isDestroyed) { cmp.update(tr('Server: unavailable')); }
            }
        });
    }

    whenDefined('FM.view.forms.SettingsForm', function (cls) {
        var proto = cls.prototype;
        if (proto.__fmForkAceNext) {
            return;
        }
        proto.__fmForkAceNext = true;
        var originalInit = proto.initComponent;
        proto.initComponent = function () {
            originalInit.apply(this, arguments);
            var tabs = this.down('tabpanel');
            if (!tabs) {
                return;
            }
            var ai = storedAi();
            tabs.add({
                title: tr('Editor+'),
                bodyPadding: 10,
                border: false,
                autoScroll: true,
                cls: 'fm-fork-editor-plus',
                defaults: {labelWidth: 150},
                items: [{
                    xtype: 'checkbox',
                    name: 'fm_fork_ace_next',
                    boxLabel: tr('New editor (Ace $1): code checking and AI suggestions', '1.45'),
                    checked: storedAceNext()
                }, {
                    xtype: 'component',
                    cls: 'fm-settings-hint',
                    margin: '0 0 8 22',
                    html: tr('By default the original editor (Ace 1.2) is used. The editor is switched after the page reloads.')
                }, {
                    xtype: 'checkbox',
                    name: 'fm_fork_ace_lint',
                    boxLabel: tr('Code checking (JS/TS, PHP, CSS/SCSS/LESS, HTML, JSON, YAML, XML, Lua)'),
                    checked: storedLint()
                }, {
                    xtype: 'radiogroup',
                    fieldLabel: tr('AI suggestions'),
                    columns: 1,
                    margin: '8 0 0 0',
                    items: [
                        {boxLabel: tr('Off'), name: 'fm_fork_ai_provider', inputValue: 'off',
                         checked: ai.provider === 'off'},
                        {boxLabel: tr('Via the server (OpenAI-compatible API)'), name: 'fm_fork_ai_provider',
                         inputValue: 'server', checked: ai.provider === 'server'},
                        {boxLabel: tr('Ollama from the browser'), name: 'fm_fork_ai_provider', inputValue: 'ollama',
                         checked: ai.provider === 'ollama'}
                    ]
                }, {
                    xtype: 'component',
                    cls: 'fm-settings-hint fm-fork-ai-server-status',
                    margin: '0 0 6 155',
                    html: ''
                }, {
                    xtype: 'textfield',
                    name: 'fm_fork_ai_ollama_url',
                    fieldLabel: tr('Ollama address'),
                    width: 420,
                    value: ai.ollamaUrl
                }, {
                    xtype: 'textfield',
                    name: 'fm_fork_ai_ollama_model',
                    fieldLabel: tr('Ollama model'),
                    width: 420,
                    value: ai.ollamaModel
                }, {
                    xtype: 'checkbox',
                    name: 'fm_fork_ai_auto',
                    boxLabel: tr('Suggest while typing (otherwise only Alt+\\)'),
                    margin: '0 0 0 155',
                    checked: ai.auto !== false
                }, {
                    xtype: 'component',
                    cls: 'fm-settings-hint',
                    margin: '6 0 0 0',
                    html: tr('Grey text after the cursor: Tab — accept, Ctrl+→ — accept a word, Esc — dismiss. For Ollama allow this site: OLLAMA_ORIGINS=$1', Ext.String.htmlEncode(window.location.origin))
                }]
            });
        };
    });

    function readAceNextForm(win) {
        function q(sel) { return Ext.ComponentQuery.query(sel, win)[0]; }
        var next = q('checkbox[name=fm_fork_ace_next]');
        if (!next) {
            return null;
        }
        var radio = q('radio[name=fm_fork_ai_provider]');
        return {
            next: next.getValue(),
            lint: q('checkbox[name=fm_fork_ace_lint]').getValue(),
            ai: {
                provider: (radio && radio.getGroupValue()) || 'off',
                auto: q('checkbox[name=fm_fork_ai_auto]').getValue(),
                delay: storedAi().delay,
                ollamaUrl: Ext.String.trim(q('textfield[name=fm_fork_ai_ollama_url]').getValue() || '') || AI_DEFAULTS.ollamaUrl,
                ollamaModel: Ext.String.trim(q('textfield[name=fm_fork_ai_ollama_model]').getValue() || '') || AI_DEFAULTS.ollamaModel
            }
        };
    }

    whenDefined('FM.view.windows.SettingsWindow', function (cls) {
        var proto = cls.prototype;
        if (proto.__fmForkAceNext) {
            return;
        }
        proto.__fmForkAceNext = true;
        var originalInit = proto.initComponent;
        proto.initComponent = function () {
            originalInit.apply(this, arguments);
            var win = this;
            win.on('beforeshow', function () {
                function q(sel) { return Ext.ComponentQuery.query(sel, win)[0]; }
                var ai = storedAi();
                var cb = q('checkbox[name=fm_fork_ace_next]');
                if (cb) {
                    cb.setValue(storedAceNext());
                    q('checkbox[name=fm_fork_ace_lint]').setValue(storedLint());
                    q('checkbox[name=fm_fork_ai_auto]').setValue(ai.auto !== false);
                    q('textfield[name=fm_fork_ai_ollama_url]').setValue(ai.ollamaUrl);
                    q('textfield[name=fm_fork_ai_ollama_model]').setValue(ai.ollamaModel);
                    var r = q('radio[name=fm_fork_ai_provider][inputValue=' + ai.provider + ']');
                    if (r) { r.setValue(true); }
                    aiServerStatus(q('component[cls~=fm-fork-ai-server-status]'));
                }
            });
            if (win.save_btn) {
                // настройки браузерные (localStorage), на сервер не уходят — применяем по «Сохранить»
                win.save_btn.on('click', function () {
                    var v = readAceNextForm(win);
                    if (!v) {
                        return;
                    }
                    var wasNext = storedAceNext();
                    var wasLint = storedLint();
                    lsSet(ACE_NEXT_KEY, v.next ? '1' : '0');
                    lsSet(ACE_LINT_KEY, v.lint ? '1' : '0');
                    lsSet(AI_KEY, JSON.stringify(v.ai));
                    var needReload = v.next !== wasNext || (v.next && v.lint !== wasLint);
                    if (needReload && Ext.ClassManager.get('FM.view.windows.QuestionWindow')) {
                        Ext.create('FM.view.windows.QuestionWindow', {
                            title: tr('Editor+'),
                            msg: tr('The editor will be switched after the page reloads.<br/>Reload now?'),
                            buttonsPreset: 'YES_NO',
                            yes: function () { window.location.reload(); },
                            no: function () { return true; }
                        }).show();
                    }
                });
            }
        };
    });

    window.FMFork = window.FMFork || {};
    window.FMFork.aceNext = {stored: storedAceNext, lint: storedLint, ai: storedAi};

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

    // родительская папка введённого пути (SFTP: относительные пути от домашнего каталога, корень — '.')
    function parentPath(path, session) {
        var sep = isWindowsPath(path) && path.indexOf('/') === -1 ? '\\' : '/';
        var idx = path.lastIndexOf(sep);
        if (idx > 0) {
            var parent = path.substring(0, idx);
            return /^[a-zA-Z]:$/.test(parent) ? parent + sep : parent;
        }
        if (idx === 0) {
            return '/';
        }
        return isSftp(session) ? '.' : null;
    }

    function baseName(path) {
        return path.replace(/[\\/]+$/, '').split(/[\\/]/).pop();
    }

    function listPath(panel, path, ok, fail) {
        FM.backend.ajaxSend('/actions/files/list', {
            params: {session: panel.session, path: path},
            success: function (response) { ok(Ext.util.JSON.decode(response.responseText).data); },
            failure: function (response) { fail(response); }
        });
    }

    function showListing(panel, listing) {
        // то же, что FileHandler.openDirectory при успешном ответе (без второго запроса)
        if (listing.path !== '/') {
            listing.items.unshift({name: '..', is_dir: true});
        }
        var app = FM.getApplication();
        app.fireEvent(FM.Events.file.listFiles, listing, [panel]);
        app.fireEvent(FM.Events.main.saveSession, [panel]);
    }

    function selectByName(panel, name) {
        var grid = panel.filelist;
        var record = grid && grid.store.findRecord('name', name, 0, false, true, true);
        if (record) {
            grid.getSelectionModel().select(record);
            grid.getView().focusRow(record);
        }
        return !!record;
    }

    // Переход по введённому пути. Путь к файлу (…/real_review/config.php) открывает его папку и выделяет файл.
    function openTypedPath(panel, path) {
        FM.helpers.SetLoading(panel.body, tr('Loading...'));
        listPath(panel, path, function (listing) {
            showListing(panel, listing);
        }, function () {
            var parent = parentPath(path, panel.session);
            var name = baseName(path);
            if (parent === null || parent === path || !name) {
                FM.helpers.UnsetLoading(panel.body);
                FM.helpers.ShowError(tr("Directory doesn't exists"));
                return;
            }
            listPath(panel, parent, function (listing) {
                var item = (listing.items || []).filter(function (i) { return i.name === name; })[0];
                if (!item || item.is_dir) {
                    FM.helpers.UnsetLoading(panel.body);
                    FM.helpers.ShowError(tr("Directory doesn't exists"));
                    return;
                }
                showListing(panel, listing);
                selectByName(panel, name);
            }, function () {
                FM.helpers.UnsetLoading(panel.body);
                FM.helpers.ShowError(tr("Directory doesn't exists"));
            });
        });
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

    // --- та же папка во второй панели (как в Total Commander) -----------------------------------------
    function mirrorToOtherPanel(panel) {
        var other = FM.helpers.NextPanel(panel);
        if (!panel || !other || !panel.session) {
            return;
        }
        var same = other.session && other.session.type === panel.session.type &&
            JSON.stringify(other.session.server_id || other.session.host) === JSON.stringify(panel.session.server_id || panel.session.host);
        if (!same) {
            // другая панель смотрит на другой сервер — переносим и подключение (сессию)
            other.session = Ext.ux.Util.clone(panel.session);
        }
        FM.Actions.Open.execute(other, panel.session.path);
    }

    // --- «Выход»: свой адрес из FM_LOGOUT_URL (window.FM_LOGOUT_URL из app.html) -----------------------
    (function patchLogout() {
        if (!(window.FM && FM.Actions && FM.Actions.Logout && FM.Actions.Logout.setHandler)) {
            setTimeout(patchLogout, 200);
            return;
        }
        FM.Actions.Logout.setHandler(function () {
            FM.backend.ajaxSend('/actions/main/logout', {
                success: function () {
                    if (window.FM_LOGOUT_URL) {
                        window.location.href = window.FM_LOGOUT_URL;
                    } else {
                        window.location.reload();     // как в оригинале — на страницу входа
                    }
                },
                failure: function () {
                    FM.helpers.ShowError(tr('Error during logout. Please contact Support.'));
                }
            });
        });
    })();

    // --- редактор и просмотр: файлы до 20 МБ (в оригинале 5 МБ) ---------------------------------------
    (function raiseMaxSize() {
        if (!(window.FM && FM.File && FM.File.MAX_SIZE)) {
            setTimeout(raiseMaxSize, 200);
            return;
        }
        FM.File.MAX_SIZE = 20 * 1024 * 1024;
    })();

    // --- симлинки: двойной клик / Enter открывают цель ------------------------------------------------
    // Оригинал игнорирует ссылки. rpc форка отдаёт link_type (dir/file/broken), link_target и link_resolved.
    // Домашний сервер: rpc видит корень хоста под /mnt, поэтому абсолютная ссылка верна только как
    // link_resolved — открываем по нему. SFTP: сервер сам ходит по ссылке — открываем путь ссылки.
    function openLink(panel, record) {
        var type = record.get('link_type') || record.data.link_type;
        var resolved = record.data.link_resolved;
        var isHome = panel.session && panel.session.type === FM.Session.HOME;
        if (type === 'broken') {
            FM.helpers.ShowError(tr('Broken link') + ': ' + (record.data.link_target || record.get('name')));
            return;
        }
        if (!type || type === 'dir') {      // без сведений о цели — как в Beget: пробуем открыть как папку
            FM.Actions.Open.execute(panel, isHome && resolved ? resolved : FM.helpers.GetAbsName(panel.session, record));
            return;
        }
        var target = record.copy();
        target.set('is_link', false);
        var proxy = panel;
        if (isHome && resolved) {
            var cut = resolved.lastIndexOf('/');
            var name = resolved.slice(cut + 1);
            target.set('name', name);
            target.set('ext', (name.lastIndexOf('.') > 0 ? name.slice(name.lastIndexOf('.') + 1) : '').toLowerCase());
            proxy = Object.create(panel);
            proxy.session = Ext.apply({}, panel.session);
            proxy.session.path = resolved.slice(0, cut) || '/';
        }
        FM.Actions.OpenFile.execute(proxy, target);
    }

    (function patchLinks() {
        if (!(window.FM && FM.Actions && FM.Actions.OpenFile && FM.Actions.OpenFile.initialConfig && FM.Actions.OpenFile.initialConfig.handler && FM.Left && FM.Right &&
              FM.Left.filelist && FM.Right.filelist)) {
            setTimeout(patchLinks, 200);
            return;
        }
        var orig = FM.Actions.OpenFile.initialConfig.handler;
        FM.Actions.OpenFile.setHandler(function (panel, record) {
            if (record && record.get('is_link')) {
                return openLink(panel, record);
            }
            return orig.apply(this, arguments);
        });
        [FM.Left, FM.Right].forEach(function (panel) {
            var view = panel.filelist.getView();
            view.on('itemmouseenter', function (v, record, item) {
                if (record.get('is_link') && record.data.link_target) {
                    item.title = record.get('name') + ' → ' + record.data.link_target;
                }
            });
            view.on('itemkeydown', function (v, record, item, index, e) {
                if (e.getKey() === Ext.event.Event.ENTER && record.get('is_link')) {
                    openLink(panel, record);
                }
            });
        });
    })();

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
                '<span class="fm-fork-mirror-btn" role="button">' + (side === 'Left' ? '⇢' : '⇠') + '</span>' +
                (side === 'Right' ? '<span class="fm-fork-menu-toggle" role="button">▾</span>' : '');
            topbar.appendChild(group);
            var input = group.querySelector('input');
            var btn = group.querySelector('.fm-fullpath-btn');
            btn.title = tr('Full path of the selected file (copied to clipboard)');
            var mirror = group.querySelector('.fm-fork-mirror-btn');
            mirror.title = tr('Open this folder in the other panel');
            mirror.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                mirrorToOtherPanel(panelBySide(side));
            });
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
                        openTypedPath(panel, path);
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
        // DataTransfer живёт только внутри обработчика — разбираем сразу (сами FileSystemEntry живут и дальше)
        var files = [];
        var entries = [];
        var hasDirs = false;
        var items = e.dataTransfer.items;
        var i;
        if (items && items.length) {
            for (i = 0; i < items.length; i++) {
                if (items[i].kind !== 'file') {
                    continue;
                }
                var entry = items[i].webkitGetAsEntry ? items[i].webkitGetAsEntry() : null;
                if (entry) {
                    entries.push(entry);
                    hasDirs = hasDirs || entry.isDirectory;
                }
                var f = items[i].getAsFile();
                if (f && !(entry && entry.isDirectory)) {
                    files.push(f);
                }
            }
        } else {
            for (i = 0; i < e.dataTransfer.files.length; i++) {
                files.push(e.dataTransfer.files[i]);
            }
        }
        if (hasDirs) {
            collectEntries(entries).then(function (tree) {
                uploadTree(panel, tree.dirs, tree.files);
            }, function (err) {
                FM.helpers.ShowError(tr('Unable to read the dropped folder: $1', String(err && err.message || err)));
            });
        } else {
            uploadDropped(panel, files);
        }
    }, false);

    // --- обход перетащенных папок: {dirs: ['a', 'a/b'], files: [{file, dir: 'a/b'}]} --------------------
    function readAllEntries(dirEntry) {
        var reader = dirEntry.createReader();
        var all = [];
        return new Promise(function (resolve, reject) {
            (function next() {
                // readEntries отдаёт содержимое порциями — читаем, пока не вернёт пустой список
                reader.readEntries(function (chunk) {
                    if (!chunk.length) {
                        resolve(all);
                        return;
                    }
                    all = all.concat(Array.prototype.slice.call(chunk));
                    next();
                }, reject);
            })();
        });
    }

    function entryFile(fileEntry) {
        return new Promise(function (resolve, reject) {
            fileEntry.file(resolve, reject);
        });
    }

    function collectEntries(entries) {
        var dirs = [];
        var files = [];
        function walk(list, prefix) {
            return list.reduce(function (chain, entry) {
                return chain.then(function () {
                    var rel = prefix ? prefix + '/' + entry.name : entry.name;
                    if (entry.isDirectory) {
                        dirs.push(rel);
                        return readAllEntries(entry).then(function (children) {
                            return walk(children, rel);
                        });
                    }
                    return entryFile(entry).then(function (file) {
                        files.push({file: file, dir: prefix});
                    });
                });
            }, Promise.resolve());
        }
        return walk(entries, '').then(function () {
            return {dirs: dirs, files: files};
        });
    }

    function newUploadDialog(panel) {
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
            return null;
        }
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
        return dialog;
    }

    function uploadDropped(panel, files) {
        if (!files.length) {
            return;
        }
        var dialog = newUploadDialog(panel);
        if (!dialog) {
            return;
        }
        dialog.queue.clearUploadedItems();
        dialog.queue.addFiles(files);
        dialog.onInitUpload();
    }

    function absPath(session, parent, name) {
        var s = Ext.apply({}, {path: parent}, session);   // Ext.apply(цель, значения, умолчания)
        return FM.helpers.GetAbsName(s, FM.model.File.create({name: name}));
    }

    function mkdir(session, path) {
        // ошибку («папка уже существует» при повторной загрузке) пропускаем: файлы всё равно лягут в неё
        return new Promise(function (resolve) {
            FM.backend.ajaxSend('/actions/files/mkdir', {
                params: {session: session, path: path},
                success: function () { resolve(true); },
                failure: function () { resolve(false); }
            });
        });
    }

    // загрузка папок со структурой: создать папки (родители раньше детей), затем каждый файл — в свою папку
    function uploadTree(panel, dirs, files) {
        if (!dirs.length && !files.length) {
            return Promise.resolve();
        }
        if (FM.Active !== panel) {
            FM.helpers.SetActivePanel(panel);
        }
        var session = Ext.ux.Util.clone(panel.session);
        var base = session.path;
        var top = {};
        dirs.forEach(function (d) { top[d.split('/')[0]] = true; });
        files.forEach(function (f) { if (!f.dir) { top[f.file.name] = true; } });
        var pseudo = Object.keys(top).map(function (name) { return {get: function () { return name; }}; });

        return new Promise(function (resolve) {
            FM.helpers.CheckOverwrite(panel, pseudo, function (overwrite) {
                var abs = {'': base};
                dirs.slice().sort(function (a, b) {
                    return a.split('/').length - b.split('/').length;
                }).forEach(function (d) {
                    var cut = d.lastIndexOf('/');
                    var parent = cut === -1 ? '' : d.substring(0, cut);
                    abs[d] = absPath(session, abs[parent], d.substring(cut + 1));
                });
                FM.helpers.SetLoading(panel.body, tr('Creating folders...'));
                Object.keys(abs).filter(function (d) { return d; }).sort(function (a, b) {
                    return a.split('/').length - b.split('/').length;
                }).reduce(function (chain, d) {
                    return chain.then(function () { return mkdir(session, abs[d]); });
                }, Promise.resolve()).then(function () {
                    FM.helpers.UnsetLoading(panel.body);
                    if (!files.length) {
                        FM.Actions.Refresh.execute();
                        resolve();
                        return;
                    }
                    var dialog = newUploadDialog(panel);
                    if (!dialog) {
                        resolve();
                        return;
                    }
                    dialog.queue.clearUploadedItems();
                    var start = dialog.queue.getCount();
                    dialog.queue.addFiles(files.map(function (f) { return f.file; }));
                    files.forEach(function (f, i) {
                        var item = dialog.queue.getAt(start + i);
                        if (item) {
                            item.fmTargetPath = abs[f.dir] || base;
                        }
                    });
                    var manager = dialog.uploadManager;
                    var uploader = manager.uploader;
                    var originalUpload = uploader.uploadItem;
                    uploader.uploadItem = function (item) {
                        // папка назначения — своя у каждого файла (параметр session запроса /upload)
                        var target = Ext.apply({}, {path: item.fmTargetPath || base}, session);
                        var encoded = Ext.JSON.encode(target);
                        manager.extraParams.session = encoded;
                        uploader.extraParams.session = encoded;
                        return originalUpload.apply(this, arguments);
                    };
                    manager.extraParams.overwrite = overwrite;
                    uploader.extraParams.overwrite = overwrite;
                    dialog.stateUpload();
                    dialog.startUpload();
                    resolve(dialog);
                });
            });
        });
    }

    // для тестов и отладки
    window.FMFork = Object.assign(window.FMFork || {}, {
        displayPath: displayPath,
        parseInputPath: parseInputPath,
        selectedFullPath: selectedFullPath,
        showFullPath: showFullPath,
        setMenuExpanded: setExpanded,
        uploadDropped: uploadDropped,
        uploadTree: uploadTree,
        mirrorToOtherPanel: mirrorToOtherPanel,
        collectEntries: collectEntries,
        openLink: openLink,
        openTypedPath: openTypedPath,
        parentPath: parentPath
    });
})();
