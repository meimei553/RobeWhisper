# -*- coding: utf-8 -*-
"""阶段 5 · 步骤 4：真机开关 + 网站展示验收。"""

from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> None:
    from core.bootstrap import create_llm, create_pipeline, create_robot
    from core.pipeline import Pipeline
    from plugins.engines.mock_engine import MockEngine
    from plugins.robot.http_robot import HttpRobot
    from plugins.robot.mock_robot import MockRobot

    # A) 未开真发：即使 backend=http 也 mock
    os.environ["ROBOT_BACKEND"] = "http"
    os.environ["USE_REAL_ROBOT"] = "false"
    os.environ["ROBOT_EXECUTE_ENDPOINT"] = "http://127.0.0.1:9/execute_task"
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)
    assert isinstance(bootstrap.create_robot(), MockRobot)

    # mock 路径 Pipeline 仍通
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["ENGINE_BACKEND"] = "mock"
    os.environ["LLM_BACKEND"] = "mock"
    reload(settings_mod)
    reload(bootstrap)
    pipe = Pipeline(llm=create_llm(), engine=MockEngine(), robot=create_robot())
    ok = pipe.run_instruction("回零")
    assert ok.ok
    assert (ok.data or {}).get("adapters", {}).get("robot") == "mock_robot"
    assert (ok.data or {}).get("robot_result", {}).get("ok") is True

    # B) 开真发 + http 假服务
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        os.environ["ROBOT_BACKEND"] = "http"
        os.environ["USE_REAL_ROBOT"] = "true"
        os.environ["ROBOT_EXECUTE_ENDPOINT"] = f"http://127.0.0.1:{port}/execute_task"
        os.environ["ENGINE_BACKEND"] = "mock"
        reload(settings_mod)
        reload(bootstrap)
        assert isinstance(bootstrap.create_robot(), HttpRobot)
        pipe2 = bootstrap.create_pipeline(engine=MockEngine())
        ok2 = pipe2.run_instruction("把红色杯子拿起来")
        assert ok2.ok
        assert (ok2.data or {}).get("adapters", {}).get("robot") == "http_robot"
        assert (ok2.data or {}).get("robot_result", {}).get("ok") is True
    finally:
        server.shutdown()

    app = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    assert "use_real_robot" in app
    assert "robot_result" in app
    assert "robot_backend" in app

    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    reload(settings_mod)
    reload(bootstrap)
    print("SMOKE_PHASE5_STEP4_OK")


if __name__ == "__main__":
    main()
