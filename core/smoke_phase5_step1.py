# -*- coding: utf-8 -*-
"""阶段 5 · 步骤 1：真机配置契约验收。"""

from __future__ import annotations

import os
import sys
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _reload():
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)
    return settings_mod, bootstrap


def main() -> None:
    from plugins.robot.mock_robot import MockRobot
    from core.schemas import TaskSpec

    # 1) 默认 mock
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    os.environ["ROBOT_EXECUTE_ENDPOINT"] = ""
    settings_mod, bootstrap = _reload()
    assert settings_mod.ROBOT_BACKEND == "mock"
    assert settings_mod.USE_REAL_ROBOT is False
    assert isinstance(bootstrap.create_robot(), MockRobot)

    # 2) 选 http 但无 endpoint → 回退 mock，不崩
    os.environ["ROBOT_BACKEND"] = "http"
    os.environ["ROBOT_EXECUTE_ENDPOINT"] = ""
    settings_mod, bootstrap = _reload()
    assert settings_mod.robot_http_configured() is False
    assert isinstance(bootstrap.create_robot(), MockRobot)

    # 3) 选 ros 且仅有 topic 字段 → configured 可为 True，但无实现时仍回退 mock
    os.environ["ROBOT_BACKEND"] = "ros"
    os.environ["ROS_DOMAIN_ID"] = "0"
    os.environ["ROS_EXECUTE_TOPIC"] = "/robewhisper/execute_task"
    settings_mod, bootstrap = _reload()
    assert settings_mod.robot_ros_configured() is True
    assert isinstance(bootstrap.create_robot(), MockRobot)

    # 4) 未知 backend → mock
    os.environ["ROBOT_BACKEND"] = "something_weird"
    _, bootstrap = _reload()
    assert isinstance(bootstrap.create_robot(), MockRobot)

    # 5) 配置字段存在性
    assert hasattr(settings_mod, "USE_REAL_ROBOT")
    assert hasattr(settings_mod, "ROBOT_EXECUTE_ENDPOINT")
    assert hasattr(settings_mod, "ROS_EXECUTE_TOPIC")
    assert hasattr(settings_mod, "ROBOT_TIMEOUT_SEC")

    env = (_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "ROBOT_BACKEND=mock" in env
    assert "USE_REAL_ROBOT" in env
    assert "ROBOT_EXECUTE_ENDPOINT" in env

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

    # 恢复默认，避免污染后续
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    _reload()

    print("SMOKE_PHASE5_STEP1_OK")


if __name__ == "__main__":
    main()
