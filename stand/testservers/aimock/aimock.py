"""Тестовый «сервер модели» для ИИ-подсказок редактора (только стенд, aimock:11434 в сети стенда).

Отвечает как Ollama (/api/generate, /api/tags) и как OpenAI-совместимый API (/v1/completions,
/v1/chat/completions). Ответ детерминированный: по последней строке текста перед курсором.
Последний запрос (тело + заголовок Authorization) — GET /_last, для проверок в тестах.
CORS — как у Ollama с OLLAMA_ORIGINS=*.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LAST = {}


def complete(prefix, suffix):
    line = prefix.split("\n")[-1]
    if line.rstrip().endswith("return"):
        text = " a + b;" if not line.endswith(" ") else "a + b;"
    elif "<CURSOR>" in prefix:
        text = "x"
    else:
        text = "// mock completion"
    if suffix.lstrip().startswith("}"):
        return text
    return text + "\n}"


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin") or "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def _json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/_last":
            return self._json(LAST)
        if self.path == "/api/tags":
            return self._json({"models": [{"name": "mock-coder"}]})
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._json({"error": "bad json"}, 400)
        LAST.clear()
        LAST.update({"path": self.path, "body": req, "auth": self.headers.get("Authorization", "")})

        if req.get("model") == "broken":
            return self._json({"error": "model 'broken' not found"}, 404)
        if self.path == "/api/generate":
            if "suffix" in req and req.get("model") == "no-insert":
                return self._json({"error": "registry.ollama.ai/library/no-insert does not support insert"}, 400)
            return self._json({"model": req.get("model"), "done": True,
                               "response": complete(req.get("prompt", ""), req.get("suffix", ""))})
        if self.path == "/v1/completions":
            return self._json({"object": "text_completion", "model": req.get("model"),
                               "choices": [{"index": 0, "text": complete(req.get("prompt", ""), req.get("suffix", "")),
                                            "finish_reason": "stop"}]})
        if self.path == "/v1/chat/completions":
            user = (req.get("messages") or [{}])[-1].get("content", "")
            before, _, after = user.partition("<CURSOR>")
            text = complete(before, after)
            return self._json({"object": "chat.completion", "model": req.get("model"),
                               "choices": [{"index": 0, "finish_reason": "stop",
                                            "message": {"role": "assistant", "content": "```js\n" + text + "\n```"}}]})
        return self._json({"error": "not found"}, 404)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 11434), Handler).serve_forever()
