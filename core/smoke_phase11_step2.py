# -*- coding: utf-8 -*-
"""第 11 期 · 步骤 2：本地假接收端 + HttpRobot 端到端烟雾。"""

from __future__ import annotations

import json
import os
import sys
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from core.schemas import TaskSpec
    from plugins.robot.http_robot import HttpRobot
    from plugins.robot.local_fake_receiver import start_server
    from plugins.robot.mock_robot import MockRobot

    # 1) 错地址：友好失败，不抛栈
    bad = HttpRobot(endpoint="http://127.0.0.1:1/execute_task", timeout_sec=1)
    r_bad = bad.execute_task(TaskSpec(task_id="t1", action="grab", target="red_cup"))
    assert not r_bad.ok
    assert r_bad.code in {"NETWORK", "TIMEOUT", "INTERNAL"}

    # 2) 本地假接收端（随机端口，不占用默认 9000）
    server, _, handler_cls = start_server(host="127.0.0.1", port=0, daemon_thread=True)
    port = int(server.server_address[1])
    endpoint = f"http://127.0.0.1:{port}/execute_task"
    try:
        ok_robot = HttpRobot(endpoint=endpoint, timeout_sec=3)
        r_ok = ok_robot.execute_task(
            TaskSpec(task_id="t2", action="home", target="", raw_text="回原点")
        )
        assert r_ok.ok, r_ok.to_dict()
        assert (r_ok.data or {}).get("ack", {}).get("ok") is True
        assert "message" in (r_ok.data or {}).get("ack", {})

        body = json.loads(handler_cls.last_body.decode("utf-8"))
        assert body["source"] == "robewhisper"
        assert body["task_spec"]["action"] == "home"

        # 3) USE_REAL_ROBOT=true + http → bootstrap 得到 HttpRobot 且能通
        os.environ["ROBOT_BACKEND"] = "http"
        os.environ["USE_REAL_ROBOT"] = "true"
        os.environ["ROBOT_EXECUTE_ENDPOINT"] = endpoint
        import config.settings as settings_mod
        import core.bootstrap as bootstrap

        reload(settings_mod)
        reload(bootstrap)
        robot = bootstrap.create_robot()
        assert isinstance(robot, HttpRobot)
        r3 = robot.execute_task(TaskSpec(task_id="t3", action="move", target=""))
        assert r3.ok, r3.to_dict()

        # 4) 对端显式 ok=false 时，HttpRobot 应失败（契约语义）
        r_reject = HttpRobot(
            endpoint=f"http://127.0.0.1:{port}/wrong_path", timeout_sec=3
        ).execute_task(TaskSpec(task_id="t4", action="grab", target="x"))
        assert not r_reject.ok
        assert r_reject.code == "REJECTED"
    finally:
        server.shutdown()
        server.server_close()

    # 5) 恢复默认：mock + 关真发 → 仍是 MockRobot（防误发）
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    os.environ["ROBOT_EXECUTE_ENDPOINT"] = ""
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)
    assert isinstance(bootstrap.create_robot(), MockRobot)
    assert bool(settings_mod.USE_REAL_ROBOT) is False

    # 6) 假接收端脚本与清单存在
    fake = _ROOT / "plugins" / "robot" / "local_fake_receiver.py"
    assert fake.is_file()
    checklist = (_ROOT / "plugins" / "robot" / "真机联调检查清单.txt").read_text(
        encoding="utf-8"
    )
    assert "local_fake_receiver" in checklist

    print("SMOKE_PHASE11_STEP2_OK", "endpoint_demo", endpoint)


if __name__ == "__main__":
    main()
