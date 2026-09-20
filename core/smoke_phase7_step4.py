# -*- coding: utf-8 -*-
"""阶段 7 · 步骤 4：真机联调检查清单验收（文档步）。"""

from __future__ import annotations

import os
import sys
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    checklist = _ROOT / "plugins/robot/真机联调检查清单.txt"
    assert checklist.exists()
    text = checklist.read_text(encoding="utf-8")
    for key in (
        "USE_REAL_ROBOT",
        "ROBOT_EXECUTE_ENDPOINT",
        "ROS_DOMAIN_ID",
        "rclpy",
        "MockRobot",
        "TaskSpec",
        "ROBOT_BACKEND",
    ):
        assert key in text, key

    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    assert "真机联调检查清单" in readme

    # 未开真发：即使写了 http 也回退 mock；契约未改
    os.environ["ROBOT_BACKEND"] = "http"
    os.environ["USE_REAL_ROBOT"] = "false"
    os.environ["ROBOT_EXECUTE_ENDPOINT"] = "http://127.0.0.1:9/execute_task"
    os.environ["ENGINE_BACKEND"] = "mock"
    os.environ["LLM_BACKEND"] = "mock"
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)
    from plugins.robot.mock_robot import MockRobot
    from core.schemas import TaskSpec

    assert isinstance(bootstrap.create_robot(), MockRobot)
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

    # 恢复安全默认，避免污染后续
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    reload(settings_mod)
    reload(bootstrap)

    print("SMOKE_PHASE7_STEP4_OK")


if __name__ == "__main__":
    main()
