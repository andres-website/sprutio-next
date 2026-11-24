/*
 * Форк sprutio: новый редактор (Ace 1.45) — проверка кода (ace-linters) и ИИ-подсказки серым текстом.
 * Подключается из app.html ТОЛЬКО при включённой галочке «Новый редактор» (localStorage 'fm-fork-ace-next' = '1');
 * иначе работает родной Ace 1.2.0 без изменений. Настройки — вкладка «Редактор+» (fm-fork.js).
 *
 * ИИ-подсказки:
 *   - 'ollama' — браузер обращается к Ollama напрямую (по умолчанию http://localhost:11434, /api/generate
 *     с prompt + suffix — FIM). Ollama должна разрешать origin файлового менеджера: OLLAMA_ORIGINS.
 *   - 'server' — через сервер файлового менеджера (/fork/ai/complete): OpenAI-совместимый API, адрес, модель
 *     и ключ — в переменных окружения app (FM_AI_*); ключ в браузер не попадает.
 * Подсказка появляется после паузы в наборе (или Alt+\), Tab — принять, Ctrl+→ — принять слово, Esc — убрать.
 */
(function () {
    // без 'use strict': как и fm-fork.js (callParent ExtJS 5 опирается на function.caller)

    var LINT_KEY = 'fm-fork-ace-lint';
    var AI_KEY = 'fm-fork-ai';
    var AI_DEFAULTS = {
        provider: 'off',                       // off | server | ollama
        auto: true,                            // подсказывать во время набора (иначе только Alt+\)
        delay: 600,                            // мс паузы перед запросом
        ollamaUrl: 'http://localhost:11434',
        ollamaModel: 'qwen2.5-coder:1.5b'
    };
    var PREFIX_MAX = 6000;
    var SUFFIX_MAX = 2000;

    function readJson(key, defaults) {
        var out = {}, k;
        for (k in defaults) { if (defaults.hasOwnProperty(k)) { out[k] = defaults[k]; } }
        try {
            var saved = JSON.parse(window.localStorage.getItem(key) || '{}');
            for (k in saved) { if (saved.hasOwnProperty(k) && out.hasOwnProperty(k)) { out[k] = saved[k]; } }
        } catch (e) { /* нет localStorage или мусор — значения по умолчанию */ }
        return out;
    }

    function aiSettings() { return readJson(AI_KEY, AI_DEFAULTS); }

    function lintEnabled() {
        try { return window.localStorage.getItem(LINT_KEY) !== '0'; } catch (e) { return true; }
    }

    function tr(text) {
        return typeof window.t === 'function' ? window.t.apply(window, arguments) : text;
    }

    function whenDefined(className, apply) {
        var tries = 0;
        (function poll() {
            var cls = window.Ext && Ext.ClassManager && Ext.ClassManager.get(className);
            if (cls) {
                apply(cls);
            } else if (tries++ < 600) {
                setTimeout(poll, 100);
            }
        })();
    }

    // emmet-core (v1, глобальный window.emmet) новому ext-emmet передаётся явно
    try {
        if (window.emmet && window.ace) {
            ace.require('ace/ext/emmet').setCore(window.emmet);
        }
    } catch (e) { /* без emmet редактор работает как обычно */ }

    // =================================================================================================
    // Проверка кода: ace-linters в web worker (сервисы грузятся с этого же сервера по мере надобности)
    // =================================================================================================
    var provider = null;

    function getProvider() {
        if (provider || !lintEnabled() || typeof window.LanguageProvider === 'undefined' || !window.Worker) {
            return provider;
        }
        try {
            provider = LanguageProvider.fromCdn(window.location.origin + '/lib/ace-linters/build', {
                functionality: {
                    hover: true,
                    completion: {overwriteCompleters: false},   // слова/сниппеты Ace остаются
                    completionResolve: true,
                    format: true,
                    documentHighlights: true,
                    signatureHelp: true,
                    codeActions: false
                }
            }, {
                // python (ruff) по умолчанию берётся с unpkg — внешний CDN не используем
                json: true, html: true, css: true, less: true, scss: true, typescript: true,
                javascript: true, lua: true, yaml: true, xml: true, php: true
            });
        } catch (e) {
            if (window.console) { console.warn('fm-ace-next: ace-linters недоступен', e); }
            provider = null;
        }
        return provider;
    }

    // =================================================================================================
    // ИИ-подсказки (ghost text)
    // =================================================================================================
    function stripFences(text) {
        var m = /^\s*```[\w+-]*\n([\s\S]*?)\n?```\s*$/.exec(text);
        return m ? m[1] : text;
    }

    function cleanCompletion(text, suffix) {
        if (typeof text !== 'string') {
            return '';
        }
        text = stripFences(text).replace(/\r\n?/g, '\n');
        // модель повторила то, что уже стоит после курсора, — отрезаем повтор
        var sufLines = suffix.split('\n');
        var rest = sufLines[0].trim();                  // остаток текущей строки
        if (rest.length > 2 && text.trim().indexOf(rest) === 0) {
            return '';
        }
        var next = '';                                  // следующая непустая строка после курсора
        for (var i = 1; i < sufLines.length && !next; i++) {
            next = sufLines[i].trim();
        }
        if (next.length > 2) {
            var lines = text.split('\n');
            for (var j = 1; j < lines.length; j++) {
                if (lines[j].trim() === next) {
                    text = lines.slice(0, j).join('\n');
                    break;
                }
            }
        }
        // хвостовые пустые строки не нужны
        return text.replace(/\n\s*$/, '');
    }

    function postJson(url, body, signal, headers) {
        var h = {'Content-Type': 'application/json'};
        for (var k in (headers || {})) { if (headers.hasOwnProperty(k)) { h[k] = headers[k]; } }
        return fetch(url, {
            method: 'POST', headers: h, body: JSON.stringify(body), signal: signal,
            credentials: url.charAt(0) === '/' ? 'same-origin' : 'omit'
        }).then(function (resp) {
            return resp.text().then(function (txt) {
                var data = null;
                try { data = JSON.parse(txt); } catch (e) { /* не JSON */ }
                if (!resp.ok) {
                    var msg = (data && (data.error || data.message)) || ('HTTP ' + resp.status);
                    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
                }
                return data || {};
            });
        });
    }

    var noInsertModels = {};   // модели Ollama без поддержки suffix — дальше просто продолжение текста

    function requestOllama(cfg, prefix, suffix, signal) {
        var url = String(cfg.ollamaUrl || AI_DEFAULTS.ollamaUrl).replace(/\/+$/, '') + '/api/generate';
        var model = cfg.ollamaModel || AI_DEFAULTS.ollamaModel;
        function ask(withSuffix) {
            var body = {
                model: model, prompt: prefix, stream: false, keep_alive: '15m',
                options: {temperature: 0.2, num_predict: 96, stop: ['\n\n\n']}
            };
            if (withSuffix) {
                body.suffix = suffix;
            }
            return postJson(url, body, signal).then(function (d) { return d.response || ''; });
        }
        if (noInsertModels[model] || !suffix) {
            return ask(false);
        }
        return ask(true).catch(function (err) {
            if (/insert|suffix/i.test(String(err && err.message))) {
                noInsertModels[model] = true;
                return ask(false);
            }
            throw err;
        });
    }

    function requestServer(prefix, suffix, language, signal) {
        return postJson('/fork/ai/complete', {prefix: prefix, suffix: suffix, language: language}, signal,
                        {'X-Requested-With': 'XMLHttpRequest'})
            .then(function (d) { return d.completion || ''; });
    }

    function AiAssist(editor, statusCmp) {
        this.editor = editor;
        this.status = statusCmp;
        this.ghost = null;          // {text, row, column}
        this.timer = null;
        this.seq = 0;
        this.abort = null;
        this.inserting = false;
        this.bind();
    }

    AiAssist.prototype.setStatus = function (text, title) {
        if (this.status && !this.status.isDestroyed) {
            this.status.setText(text || '');
            if (this.status.el) {
                this.status.el.dom.title = title || '';
            }
        }
    };

    AiAssist.prototype.cfg = function () { return aiSettings(); };

    AiAssist.prototype.enabled = function () { return this.cfg().provider !== 'off'; };

    AiAssist.prototype.clear = function () {
        if (this.ghost) {
            this.ghost = null;
            try { this.editor.removeGhostText(); } catch (e) { /* старый Ace — нет ghost text */ }
            this.setStatus(this.enabled() ? tr('AI') : '');
        }
    };

    AiAssist.prototype.cancel = function () {
        clearTimeout(this.timer);
        this.timer = null;
        this.seq++;
        if (this.abort) {
            try { this.abort.abort(); } catch (e) { /* уже завершён */ }
            this.abort = null;
        }
    };

    AiAssist.prototype.schedule = function () {
        var cfg = this.cfg();
        this.cancel();
        if (cfg.provider === 'off' || !cfg.auto) {
            return;
        }
        var self = this;
        this.timer = setTimeout(function () { self.request(false); }, Math.max(150, +cfg.delay || 600));
    };

    AiAssist.prototype.request = function (manual) {
        var editor = this.editor, cfg = this.cfg(), self = this;
        if (cfg.provider === 'off') {
            if (manual) { this.setStatus(tr('AI is off'), tr('Settings → Editor+')); }
            return;
        }
        if (!editor.selection.isEmpty() || (editor.completer && editor.completer.activated)) {
            return;
        }
        var pos = editor.getCursorPosition();
        var doc = editor.session.getDocument();
        var lines = doc.getAllLines();
        var before = lines.slice(0, pos.row).concat([lines[pos.row].slice(0, pos.column)]).join('\n');
        var after = [lines[pos.row].slice(pos.column)].concat(lines.slice(pos.row + 1)).join('\n');
        // в середине слова (справа буква/цифра) не подсказываем автоматически
        if (!manual && /^\w/.test(after)) {
            return;
        }
        var prefix = before.slice(-PREFIX_MAX);
        var suffix = after.slice(0, SUFFIX_MAX);
        var language = (editor.session.$modeId || '').replace('ace/mode/', '');

        this.cancel();
        var my = ++this.seq;
        this.abort = window.AbortController ? new AbortController() : null;
        var signal = this.abort ? this.abort.signal : undefined;
        this.setStatus(tr('AI…'));

        var p = cfg.provider === 'ollama'
            ? requestOllama(cfg, prefix, suffix, signal)
            : requestServer(prefix, suffix, language, signal);

        p.then(function (text) {
            if (my !== self.seq) {
                return;
            }
            self.abort = null;
            var now = editor.getCursorPosition();
            if (now.row !== pos.row || now.column !== pos.column) {
                return;
            }
            text = cleanCompletion(text, suffix);
            if (!text.replace(/\s/g, '')) {
                self.setStatus(tr('AI'), manual ? tr('No suggestion') : '');
                return;
            }
            self.show(text, pos);
        }, function (err) {
            if (my !== self.seq || (err && err.name === 'AbortError')) {
                return;
            }
            self.abort = null;
            var msg = String(err && err.message || err);
            self.setStatus(tr('AI: error'), msg);
            if (window.console) { console.warn('fm-ace-next: AI', msg); }
        });
    };

    AiAssist.prototype.show = function (text, pos) {
        this.ghost = {text: text, row: pos.row, column: pos.column};
        this.editor.setGhostText(text, {row: pos.row, column: pos.column});
        this.setStatus(tr('AI: Tab — accept'), tr('Tab — accept, Ctrl+→ — accept a word, Esc — dismiss'));
    };

    AiAssist.prototype.accept = function (wordOnly) {
        if (!this.ghost) {
            return false;
        }
        var text = this.ghost.text;
        if (wordOnly) {
            var m = /^\s*[^\s]+?(?=\W|$)\W?|^\s+/.exec(text);
            text = m ? m[0] : text;
        }
        var rest = this.ghost.text.slice(text.length);
        var pos = {row: this.ghost.row, column: this.ghost.column};
        this.clear();
        this.inserting = true;
        try {
            this.editor.session.insert(pos, text);
        } finally {
            this.inserting = false;
        }
        if (rest) {
            this.show(rest, this.editor.getCursorPosition());
        }
        return true;
    };

    AiAssist.prototype.bind = function () {
        var self = this, editor = this.editor;

        editor.commands.addCommand({
            name: 'fmAiAccept',
            bindKey: {win: 'Tab', mac: 'Tab'},
            exec: function () { return self.accept(false); }   // false → Tab работает как обычно
        });
        editor.commands.addCommand({
            name: 'fmAiAcceptWord',
            bindKey: {win: 'Ctrl-Right', mac: 'Alt-Right'},
            exec: function () { return self.accept(true); }
        });
        editor.commands.addCommand({
            name: 'fmAiDismiss',
            bindKey: {win: 'Esc', mac: 'Esc'},
            exec: function () {
                if (!self.ghost) { return false; }
                self.cancel();
                self.clear();
                return true;
            }
        });
        editor.commands.addCommand({
            name: 'fmAiSuggest',
            bindKey: {win: 'Alt-\\', mac: 'Alt-\\'},
            exec: function () { self.clear(); self.request(true); return true; }
        });

        this.onChange = function (delta) {
            if (self.inserting) {
                return;
            }
            self.clear();
            // подсказка — после ввода текста, не после удаления
            if (delta && delta.action === 'insert' && editor.isFocused()) {
                self.schedule();
            } else {
                self.cancel();
            }
        };
        this.onCursor = function () {
            if (self.inserting) {
                return;
            }
            if (self.ghost) {
                var c = editor.getCursorPosition();
                if (c.row !== self.ghost.row || c.column !== self.ghost.column) {
                    self.cancel();
                    self.clear();
                }
            }
        };
        this.onBlur = function () { self.cancel(); };
        editor.session.on('change', this.onChange);
        editor.selection.on('changeCursor', this.onCursor);
        editor.on('blur', this.onBlur);
        this.setStatus(this.enabled() ? tr('AI') : '', this.enabled() ? tr('Alt+\\ — ask for a suggestion') : '');
    };

    AiAssist.prototype.destroy = function () {
        this.cancel();
        this.clear();
        var editor = this.editor;
        editor.session.off('change', this.onChange);
        editor.selection.off('changeCursor', this.onCursor);
        editor.off('blur', this.onBlur);
        ['fmAiAccept', 'fmAiAcceptWord', 'fmAiDismiss', 'fmAiSuggest'].forEach(function (n) {
            editor.commands.removeCommand(n);
        });
    };

    // =================================================================================================
    // Подключение к окну редактора (просмотрщик не трогаем)
    // =================================================================================================
    whenDefined('FM.view.windows.EditorWindow', function (cls) {
        var proto = cls.prototype;
        if (proto.__fmAceNext) {
            return;
        }
        proto.__fmAceNext = true;
        var originalInit = proto.initEditor;

        proto.initEditor = function (aceEditor) {
            var result = originalInit.apply(this, arguments);
            var win = this;
            win.addCls('fm-ace-next');

            var bbar = win.getDockedItems('toolbar[dock="bottom"]')[0];
            var status = null;
            if (bbar) {
                var idx = bbar.items.findIndexBy(function (i) { return i.cls === 'fm-editor-status'; });
                status = Ext.create('Ext.toolbar.TextItem', {cls: 'fm-ai-status', text: ''});
                bbar.insert(idx >= 0 ? idx : bbar.items.getCount(), [status, '-']);
            }
            win.fmAi = new AiAssist(aceEditor, status);

            var lp = getProvider();
            if (lp) {
                try {
                    lp.registerEditor(aceEditor);
                    win.fmLint = lp;
                } catch (e) {
                    if (window.console) { console.warn('fm-ace-next: registerEditor', e); }
                }
            }

            win.on('destroy', function () {
                if (win.fmAi) {
                    win.fmAi.destroy();
                    win.fmAi = null;
                }
                if (win.fmLint) {
                    try { win.fmLint.unregisterEditor(aceEditor, true); } catch (e) { /* уже закрыт */ }
                    win.fmLint = null;
                }
            });
            return result;
        };
    });

    window.FMAceNext = {
        version: window.ace && ace.version,
        aiSettings: aiSettings,
        lintEnabled: lintEnabled,
        getProvider: getProvider,
        cleanCompletion: cleanCompletion,
        AiAssist: AiAssist
    };
})();
