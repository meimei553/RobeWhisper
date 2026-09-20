# -*- coding: utf-8 -*-
"""阶段 5 · 步骤 2：HttpRobot 验收。"""

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
    last_body: bytes = b""

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        _Handler.last_body = self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok","accepted":true}')

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> None:
    from core.schemas import TaskSpec
    from plugins.robot.http_robot import HttpRobot
    from plugins.robot.mock_robot import MockRobot

    # 错地址：友好失败，不抛异常
    bad = HttpRobot(endpoint="http://127.0.0.1:1/execute_task", timeout_sec=1)
    r_bad = bad.execute_task(TaskSpec(task_id="t1", action="grab", target="red_cup"))
    assert not r_bad.ok
    assert r_bad.code in {"NETWORK", "TIMEOUT", "INTERNAL"}

    # 本地假接收端
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        ok = HttpRobot(endpoint=f"http://127.0.0.1:{port}/execute_task", timeout_sec=3)
        r_ok = ok.execute_task(TaskSpec(task_id="t2", action="home", target=""))
        assert r_ok.ok, r_ok.to_dict()
        body = json.loads(_Handler.last_body.decode("utf-8"))
        assert body["task_spec"]["action"] == "home"

        # bootstrap：配置齐全且允许真发时应得到 HttpRobot
        os.environ["ROBOT_BACKEND"] = "http"
        os.environ["USE_REAL_ROBOT"] = "true"
        os.environ["ROBOT_EXECUTE_ENDPOINT"] = f"http://127.0.0.1:{port}/execute_task"
        import config.settings as settings_mod
        import core.bootstrap as bootstrap

        reload(settings_mod)
        reload(bootstrap)
        robot = bootstrap.create_robot()
        assert isinstance(robot, HttpRobot)
        r3 = robot.execute_task(TaskSpec(task_id="t3", action="move", target=""))
        assert r3.ok
    finally:
        server.shutdown()

    # 无 endpoint 时 create_robot 回退 mock
    os.environ["ROBOT_BACKEND"] = "http"
    os.environ["ROBOT_EXECUTE_ENDPOINT"] = ""
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)
    assert isinstance(bootstrap.create_robot(), MockRobot)

    # 恢复
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    reload(settings_mod)
    reload(bootstrap)

    pipe_src = (_ROOT / "core/pipeline.py").read_text(encoding="utf-8")
    assert "HttpRobot" not in pipe_src
    print("SMOKE_PHASE5_STEP2_OK")


if __name__ == "__main__":
    main()
