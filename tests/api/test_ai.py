"""ИИ-подсказки редактора через сервер: /fork/ai/status и /fork/ai/complete (OpenAI-совместимый API).

На стенде модель — тестовый сервер aimock (stand/testservers/aimock), FM_AI_* — в stand/.env.
"""
import json
import subprocess

import pytest
import requests

from fmclient import BASE

pytestmark = pytest.mark.fork_only("ИИ-подсказки в редакторе")

MOCK = "http://127.0.0.1:11435"


def mock_last():
    return requests.get(MOCK + "/_last", timeout=5).json()


@pytest.fixture(scope="module")
def ai_ready(fm):
    st = fm.s.get(fm.base + "/fork/ai/status", timeout=10)
    assert st.status_code == 200, st.text
    data = st.json()
    if not data.get("enabled"):
        pytest.skip("FM_AI_* на стенде не заданы")
    try:
        requests.get(MOCK + "/api/tags", timeout=3)
    except requests.RequestException:
        pytest.skip("aimock не запущен")
    return data


def test_requires_login():
    anon = requests.Session()
    anon.verify = False
    r = anon.get(BASE + "/fork/ai/status", allow_redirects=False, timeout=10)
    assert r.status_code == 401
    r = anon.post(BASE + "/fork/ai/complete", data=json.dumps({"prefix": "x"}), allow_redirects=False, timeout=10)
    assert r.status_code == 401


def test_status_hides_key(fm, ai_ready):
    r = fm.s.get(fm.base + "/fork/ai/status", timeout=10)
    data = r.json()
    assert data == {"enabled": True, "model": "mock-coder", "api": "completions"}
    assert "key" not in r.text.lower() and "aimock" not in r.text


def test_complete_fim(fm, ai_ready):
    r = fm.s.post(fm.base + "/fork/ai/complete",
                   data=json.dumps({"prefix": "function add(a, b) {\n  return ", "suffix": "\n}\n",
                                    "language": "javascript"}), timeout=30)
    assert r.status_code == 200, r.text
    assert r.json() == {"completion": "a + b;"}
    last = mock_last()
    assert last["path"] == "/v1/completions"
    assert last["body"]["model"] == "mock-coder"
    assert last["body"]["prompt"].endswith("return ") and last["body"]["suffix"] == "\n}\n"
    assert last["auth"].startswith("Bearer ") and len(last["auth"]) > 8   # ключ из окружения, браузер его не знает


def test_complete_limits_and_bad_input(fm, ai_ready):
    big = "x" * 50000
    r = fm.s.post(fm.base + "/fork/ai/complete", data=json.dumps({"prefix": big, "suffix": big}), timeout=30)
    assert r.status_code == 200
    last = mock_last()
    assert len(last["body"]["prompt"]) == 16000 and len(last["body"]["suffix"]) == 8000
    r = fm.s.post(fm.base + "/fork/ai/complete", data="not json", timeout=10)
    assert r.status_code == 400
    r = fm.s.post(fm.base + "/fork/ai/complete", data="[1, 2]", timeout=10)
    assert r.status_code == 400


def _app_env_exec(code):
    """Запустить кусок Python внутри контейнера app с другими FM_AI_* (проверка режима chat и ошибок)."""
    out = subprocess.run(["docker", "exec", "sprutio-app-1", "sh", "-c", code], capture_output=True, text=True,
                         timeout=60)
    return out


def test_chat_mode_and_model_error(ai_ready):
    script = (
        "cd /app && FM_AI_BASE_URL=http://aimock:11434/v1 FM_AI_MODEL=%s FM_AI_API=chat "
        "python3 -c \"from handlers.fork.AiHandler import ai_config, request_completion; "
        "print(repr(request_completion(ai_config(), 'function f() {\\n  return', '\\n}', 'javascript')))\""
    )
    ok = _app_env_exec(script % "mock-coder")
    if ok.returncode != 0 and "No such container" in ok.stderr:
        pytest.skip("контейнер app называется иначе")
    assert ok.returncode == 0, ok.stderr
    assert ok.stdout.strip() == repr(" a + b;")       # ```-ограждение из ответа чата снято
    assert mock_last()["path"] == "/v1/chat/completions"
    bad = _app_env_exec(script % "broken")
    assert bad.returncode != 0 and "HTTPError" in bad.stderr
