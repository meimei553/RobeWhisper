# -*- coding: utf-8 -*-
"""阶段 5 总复验。用法：python -m core.smoke_phase5"""

from __future__ import annotations

import os
import urllib.request
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    os.environ["ENGINE_BACKEND"] = "mujoco"
    os.environ["LLM_BACKEND"] = "mock"
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)

    from config import settings
    from core.bootstrap import create_pipeline, create_robot
    from core.schemas import TaskSpec
    from plugins.robot.http_robot import HttpRobot
    from plugins.robot.mock_robot import MockRobot
    from plugins.robot.ros_robot import RosRobot

    assert hasattr(settings, "USE_REAL_ROBOT")
    assert hasattr(settings, "ROBOT_EXECUTE_ENDPOINT")
    assert isinstance(create_robot(), MockRobot)

    pipe = create_pipeline()
    ok = pipe.run_instruction("把红色杯子拿起来")
    assert ok.ok
    assert (ok.data or {}).get("adapters", {}).get("robot") == "mock_robot"

    # 模块存在
    assert (_ROOT / "plugins/robot/http_robot.py").exists()
    assert (_ROOT / "plugins/robot/ros_robot.py").exists()
    assert (_ROOT / "plugins/robot/ROS接入说明.txt").exists()

    app = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    assert "use_real_robot" in app and "robot_result" in app

    assert set(TaskSpec(task_id="a", action="m").to_dict()) == {
        "task_id",
        "action",
        "target",
        "constraints",
        "params",
        "source",
        "raw_text",
        "steps",
    }

    # 类型可导入
    assert HttpRobot and RosRobot

    try:
        with urllib.request.urlopen("http://127.0.0.1:8501", timeout=5) as resp:
            assert resp.status == 200
        site = "UP"
    except Exception:
        site = "DOWN"

    print("PHASE5_ACCEPTANCE_PASS", "site", site)


if __name__ == "__main__":
    main()
