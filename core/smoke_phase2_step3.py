# -*- coding: utf-8 -*-
"""阶段 2 · 步骤 3：物理参数面板逻辑验收。"""

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
    from plugins.engines.mujoco_engine import MujocoEngine

    eng = bootstrap.create_engine()
    assert isinstance(eng, MujocoEngine)
    eng.load("default")
    eng.reset()

    before = eng.list_physics_params()
    after = eng.set_physics_params(
        {
            "friction": 0.15,
            "joint_damping": 2.0,
            "joint_range_min": -1.2,
            "joint_range_max": 1.2,
            "not_allowed": 123,
        }
    )
    assert abs(float(after["friction"]) - 0.15) < 1e-6
    assert abs(float(after["joint_damping"]) - 2.0) < 1e-6
    assert abs(float(after["joint_range_min"]) - (-1.2)) < 1e-6
    assert abs(float(after["joint_range_max"]) - 1.2) < 1e-6
    assert "not_allowed" in after.get("skipped", [])
    assert abs(float(before["friction"]) - float(after["friction"])) > 1e-6 or abs(
        float(before["joint_damping"]) - float(after["joint_damping"])
    ) > 1e-6

    # 再次 list 应读到新值
    again = eng.list_physics_params()
    assert abs(float(again["friction"]) - 0.15) < 1e-6

    # 改参后仍可步进
    b = eng.get_state()["joint_positions"]
    a = eng.step({"joint_targets": [0.5, -0.4], "nsub": 30})["joint_positions"]
    assert sum(abs(float(x) - float(y)) for x, y in zip(b, a)) > 1e-3

    app = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    assert "set_physics_params" in app and "list_physics_params" in app
    assert "import mujoco" not in app
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

    print("SMOKE_PHASE2_STEP3_OK")
    print("friction", before.get("friction"), "->", after.get("friction"))
    print("damping", before.get("joint_damping"), "->", after.get("joint_damping"))


if __name__ == "__main__":
    main()
