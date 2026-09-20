# -*- coding: utf-8 -*-
"""能力可见 · 步骤3：API 只读自检。"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _start_fake_chat_server(*, status: int = 200, body: dict | None = None) -> tuple[HTTPServer, str]:
    """本机假 Chat Completions，供无外网烟雾。"""
    payload = body if body is not None else {
        "choices": [{"message": {"content": "通"}}],
    }
    raw = json.dumps(payload).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            _ = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = int(server.server_address[1])
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{port}/v1"
    return server, base


def main() -> None:
    from core.llm_api_probe import (
        missing_llm_api_items,
        probe_llm_api,
        redact_api_base,
        redact_api_key_hint,
    )

    # 缺项：不发网，直接说缺什么
    miss = missing_llm_api_items(api_base="", api_key="x", model_name="")
    assert "地址 LLM_API_BASE" in miss
    assert "模型名 LLM_MODEL_NAME" in miss
    assert "密钥 LLM_API_KEY" not in miss

    empty = probe_llm_api(
        api_base="",
        api_key="",
        model_name="",
        use_settings=False,
    )
    assert empty["ok"] is False
    assert empty["code"] == "NOT_CONFIGURED"
    assert "缺" in empty["message"]
    assert empty["read_only"] is True
    assert "sk-" not in json.dumps(empty, ensure_ascii=False)

    # 脱敏：密钥原文不得出现在结果里
    secret = "sk-this-must-never-leak-1234567890"
    hint = redact_api_key_hint(secret)
    assert secret not in hint
    assert "已填" in hint
    red = redact_api_base("https://api.example.com/v1")
    assert "api.example.com" in red["display"]

    # 假服务：200 + choices → OK
    srv, base = _start_fake_chat_server()
    try:
        ok = probe_llm_api(
            api_base=base,
            api_key="sk-fake-for-smoke-only-not-real",
            model_name="smoke-model",
            timeout_sec=3.0,
            use_settings=False,
        )
        assert ok["ok"] is True, ok
        assert ok["code"] == "OK"
        assert "通" in ok["message"] or "成功" in ok["message"]
        blob = json.dumps(ok, ensure_ascii=False)
        assert "sk-fake" not in blob
        assert ok["key_hint"] != "sk-fake-for-smoke-only-not-real"
    finally:
        srv.shutdown()

    # 假服务：401 → AUTH 人话
    srv401, base401 = _start_fake_chat_server(status=401, body={"error": {"message": "bad key"}})
    try:
        bad = probe_llm_api(
            api_base=base401,
            api_key="sk-wrong-key-aaaaaaaa",
            model_name="smoke-model",
            timeout_sec=3.0,
            use_settings=False,
        )
        assert bad["ok"] is False
        assert bad["code"] == "AUTH"
        assert "密钥" in bad["message"]
        assert "sk-wrong" not in json.dumps(bad, ensure_ascii=False)
    finally:
        srv401.shutdown()

    # 假服务：429 → QUOTA 友好失败
    srv429, base429 = _start_fake_chat_server(status=429, body={"error": {"message": "insufficient"}})
    try:
        quota = probe_llm_api(
            api_base=base429,
            api_key="sk-quota-key-bbbbbbbb",
            model_name="smoke-model",
            timeout_sec=3.0,
            use_settings=False,
        )
        assert quota["ok"] is False
        assert quota["code"] == "QUOTA"
        assert "额度" in quota["message"] or "充值" in quota["message"]
    finally:
        srv429.shutdown()

    # 网站已接入按钮与探测
    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    assert "probe_llm_api" in app
    assert "自检云端 API 是否通" in app
    assert "不展示密钥" in app or "不展示完整密钥" in app or "密钥原文" in app

    print("SMOKE_FEATURE_VISIBLE_STEP3_OK")


if __name__ == "__main__":
    main()
