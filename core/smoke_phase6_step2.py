# -*- coding: utf-8 -*-
"""阶段 6 · 步骤 2：参数校准器验收。"""

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
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)

    from core.param_calibrator import apply_calibration_to_engine, propose_param_updates
    from core.schemas import TaskSpec
    from core.trajectory_metrics import compute_trajectory_deviation

    # 纯函数建议
    prop = propose_param_updates(
        {"friction": 1.0, "joint_damping": 0.5},
        {"ok": True, "mae": 0.2},
    )
    assert prop["ok"] and prop["updated"]
    assert prop["after"]["joint_damping"] > prop["before"]["joint_damping"]

    tiny = propose_param_updates(
        {"friction": 1.0, "joint_damping": 0.5},
        {"ok": True, "mae": 1e-6},
    )
    assert tiny["ok"] and not tiny["updated"]

    # 写回真引擎
    eng = bootstrap.create_engine()
    eng.load("default")
    before = eng.list_physics_params()
    sim = [
        {"t": 0, "joint_positions": [0.0, 0.0]},
        {"t": 1, "joint_positions": [0.2, -0.1]},
    ]
    real = [
        {"t": 0, "joint_positions": [0.0, 0.0]},
        {"t": 1, "joint_positions": [0.5, -0.4]},
    ]
    dev = compute_trajectory_deviation(sim, real)
    result = apply_calibration_to_engine(eng, dev, gain=0.8)
    assert result["ok"] and result["updated"], result
    after = eng.list_physics_params()
    assert abs(float(after["joint_damping"]) - float(before["joint_damping"])) > 1e-6 or abs(
        float(after["friction"]) - float(before["friction"])
    ) > 1e-6

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
    print(
        "SMOKE_PHASE6_STEP2_OK",
        "damp",
        round(float(before["joint_damping"]), 3),
        "->",
        round(float(after["joint_damping"]), 3),
    )


if __name__ == "__main__":
    main()
