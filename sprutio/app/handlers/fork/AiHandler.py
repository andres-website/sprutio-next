# Форк: ИИ-подсказки в редакторе через сервер (OpenAI-совместимый API).
#
# Браузер присылает текст до и после курсора, сервер спрашивает модель и отдаёт вставку. Адрес, модель и ключ
# задаются в окружении контейнера app и в браузер не попадают:
#   FM_AI_BASE_URL   — например https://api.openai.com/v1, http://ollama:11434/v1, http://llama:8080/v1
#   FM_AI_MODEL      — имя модели
#   FM_AI_API_KEY    — ключ (Authorization: Bearer), можно пусто для локальных серверов
#   FM_AI_API        — completions (по умолчанию: /completions с prompt + suffix, FIM) | chat (/chat/completions)
#   FM_AI_MAX_TOKENS — длина подсказки (96), FM_AI_TIMEOUT — секунды (30)
# Пустой FM_AI_BASE_URL или FM_AI_MODEL — подсказки через сервер выключены.
import json
import logging
import os
import re
import urllib.error
import urllib.request

from handlers.BaseHandler import BaseHandler, wrap_async_rpc, wrap_catch

PREFIX_MAX = 16000
SUFFIX_MAX = 8000

CHAT_SYSTEM = ("You are a code completion engine inside a text editor. The user sends a file with the marker "
               "<CURSOR> where the cursor is. Reply ONLY with the text to insert at <CURSOR>: no explanations, "
               "no markdown fences, do not repeat text that is already before or after the cursor. "
               "Keep it short: finish the current statement or a few lines at most.")

logger = logging.getLogger('tornado.application')


def ai_config():
    base = os.getenv("FM_AI_BASE_URL", "").strip().rstrip("/")
    model = os.getenv("FM_AI_MODEL", "").strip()
    api = os.getenv("FM_AI_API", "completions").strip().lower()
    if api not in ("completions", "chat"):
        api = "completions"

    def num(name, default):
        try:
            return max(1, int(os.getenv(name, default)))
        except ValueError:
            return default

    return {
        "enabled": bool(base and model),
        "base": base,
        "model": model,
        "key": os.getenv("FM_AI_API_KEY", "").strip(),
        "api": api,
        "max_tokens": num("FM_AI_MAX_TOKENS", 96),
        "timeout": num("FM_AI_TIMEOUT", 30),
    }


def strip_fences(text):
    m = re.match(r"^\s*```[\w+-]*\n(.*?)\n?```\s*$", text, re.S)
    return m.group(1) if m else text


def request_completion(cfg, prefix, suffix, language):
    if cfg["api"] == "chat":
        url = cfg["base"] + "/chat/completions"
        lang = (" (" + language + ")") if language else ""
        body = {
            "model": cfg["model"],
            "messages": [
                {"role": "system", "content": CHAT_SYSTEM},
                {"role": "user", "content": "File" + lang + ":\n" + prefix + "<CURSOR>" + suffix},
            ],
            "max_tokens": cfg["max_tokens"],
            "temperature": 0.2,
            "stream": False,
        }
    else:
        url = cfg["base"] + "/completions"
        body = {
            "model": cfg["model"],
            "prompt": prefix,
            "suffix": suffix,
            "max_tokens": cfg["max_tokens"],
            "temperature": 0.2,
            "stop": ["\n\n\n"],
            "stream": False,
        }

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if cfg["key"]:
        headers["Authorization"] = "Bearer " + cfg["key"]
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    choice = (data.get("choices") or [{}])[0]
    if cfg["api"] == "chat":
        text = (choice.get("message") or {}).get("content") or ""
        text = strip_fences(text)
    else:
        text = choice.get("text") or ""
    return text


class AiStatusHandler(BaseHandler):

    @wrap_async_rpc
    @wrap_catch
    def get(self):
        if not self.get_current_user():
            return self.reply({"error": "unauthorized"}, 401)
        cfg = ai_config()
        self.reply({"enabled": cfg["enabled"], "model": cfg["model"] if cfg["enabled"] else "",
                    "api": cfg["api"] if cfg["enabled"] else ""})

    def reply(self, data, code=200):
        self.set_status(code)
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        self.set_header("Cache-Control", "no-store")
        self.write(json.dumps(data, ensure_ascii=False))
        self.finish()


class AiCompleteHandler(AiStatusHandler):

    @wrap_async_rpc
    @wrap_catch
    def post(self):
        if not self.get_current_user():
            return self.reply({"error": "unauthorized"}, 401)
        cfg = ai_config()
        if not cfg["enabled"]:
            return self.reply({"error": "AI is not configured on the server"}, 503)
        try:
            params = json.loads(self.request.body.decode("utf-8") or "{}")
        except ValueError:
            return self.reply({"error": "bad request"}, 400)
        if not isinstance(params, dict):
            return self.reply({"error": "bad request"}, 400)

        prefix = str(params.get("prefix") or "")[-PREFIX_MAX:]
        suffix = str(params.get("suffix") or "")[:SUFFIX_MAX]
        language = re.sub(r"[^\w+#.-]", "", str(params.get("language") or ""))[:40]

        try:
            text = request_completion(cfg, prefix, suffix, language)
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            logger.warning("fork AI: HTTP %s from model server", e.code)
            return self.reply({"error": "model server: HTTP %s %s" % (e.code, detail)}, 502)
        except Exception as e:  # сеть, таймаут, неожиданный ответ — текст файла в лог не пишем
            logger.warning("fork AI: %s", e.__class__.__name__)
            return self.reply({"error": "model server: " + e.__class__.__name__ + ": " + str(e)[:200]}, 502)

        self.reply({"completion": text})
