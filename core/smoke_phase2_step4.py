# -*- coding: utf-8 -*-
"""阶段 2 · 步骤 4：整站闭环验收（选模型→参数→步进）。"""

from __future__ import annotations

import os
import sys
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    os.environ["ENGINE_BACKEND"] = "mujoco"
    import config.settings as settings_mod

    reload(settings_mod)
    import core.bootstrap as bootstrap

    reload(bootstrap)

    from core.schemas import TaskSpec
    from core.sim_workflow import run_closed_loop
    from plugins.engines.mujoco_engine import MujocoEngine

    eng = bootstrap.create_engine()
    assert isinstance(eng, MujocoEngine)

    # 默认模型闭环
    r1 = run_closed_loop(
        eng,
        model_ref="default",
        physics={
            "friction": 0.25,
            "joint_damping": 1.2,
            "joint_range_min": -1.5,
            "joint_range_max": 1.5,
        },
        joint_targets=[0.6, -0.5],
        nsub=40,
    )
    assert r1["ok"] and r1["moved"], r1

    # 切换另一模型再闭环
    r2 = run_closed_loop(
        eng,
        model_ref="mujoco_testdata/model.xml",
        physics={"friction": 0.5},
        nsub=20,
    )
    assert r2["ok"], r2

    # 回退 default
    r3 = run_closed_loop(eng, model_ref="default", physics={"friction": 0.8}, joint_targets=[0.3, -0.2])
    assert r3["ok"] and r3["moved"], r3

    app = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    assert "import mujoco" not in app
    assert "flow_model_ok" in app and "应用物理参数" in app and "应用并步进" in app
    assert "run_closed_loop" not in app  # 页面保持直接调适配器；工作流脚本供验收
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

    print("SMOKE_PHASE2_STEP4_OK")
    print("moved_default", r1["moved"], "testdata_ok", r2["ok"], "back_default", r3["moved"])


if __name__ == "__main__":
    main()
