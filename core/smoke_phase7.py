# -*- coding: utf-8 -*-
"""阶段 7 总复验。用法：python -m core.smoke_phase7"""

from __future__ import annotations

import os
import urllib.request
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    for rel in (
        "README.md",
        "安装依赖.bat",
        "一键启动网站.bat",
        "frontend/app.py",
        "frontend/reply_text.py",
        "plugins/robot/真机联调检查清单.txt",
        "core/演示剧本.txt",
        "core/回归与启动一页纸.txt",
        "core/二期边界.txt",
        "core/阶段7验收.txt",
        "core/smoke_phase7_step1.py",
        "core/smoke_phase7_step2.py",
        "core/smoke_phase7_step3.py",
        "core/smoke_phase7_step4.py",
        "core/safety_gate.py",
        "core/总规划_不超过15期.md",
    ):
        assert (_ROOT / rel).exists(), rel

    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    assert "127.0.0.1:8501" in readme
    assert "一键启动网站.bat" in readme
    assert not (_ROOT / "install_autostart.bat").exists()

    app = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    assert "已具备能力一览" in app
    assert "experiments_table_rows" in app
    assert "browse_tables" in app
    assert "rsr_enable_ui" in app

    os.environ["ENGINE_BACKEND"] = "mujoco"
    os.environ["LLM_BACKEND"] = "mock"
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    os.environ["USE_REAL_SIM_REAL"] = "false"
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)

    from core.schemas import TaskSpec
    from plugins.robot.mock_robot import MockRobot

    assert isinstance(bootstrap.create_robot(), MockRobot)
    pipe = bootstrap.create_pipeline()
    ok = pipe.run_instruction("把红色杯子拿起来")
    assert ok.ok
    assert "rsr" not in (ok.data or {})

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

    try:
        with urllib.request.urlopen("http://127.0.0.1:8501", timeout=5) as resp:
            assert resp.status == 200
        site = "UP"
    except Exception:
        site = "DOWN"

    print("PHASE7_ACCEPTANCE_PASS", "site", site)


if __name__ == "__main__":
    main()
