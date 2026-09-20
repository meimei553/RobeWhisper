# -*- coding: utf-8 -*-
"""阶段 2 总复验。用法：python -m core.smoke_phase2"""

from __future__ import annotations

import os
import urllib.request
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    os.environ["ENGINE_BACKEND"] = "mujoco"
    import config.settings as settings_mod

    reload(settings_mod)
    import core.bootstrap as bootstrap

    reload(bootstrap)

    from core.schemas import ApiResult, SimResult, TaskSpec
    from core.sim_workflow import run_closed_loop
    from plugins.engines.mujoco_engine import MujocoEngine

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
    assert set(SimResult(task_id="a", ok=True).to_dict()) == {
        "task_id",
        "ok",
        "trajectory",
        "metrics",
        "message",
        "engine_name",
        "engine_version",
    }
    assert set(ApiResult.success().to_dict()) == {"ok", "code", "message", "data"}

    app = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    assert "import mujoco" not in app
    assert "list_model_options" in app and "set_physics_params" in app
    # 阶段3起允许聊天区；阶段2能力（导入/参数）仍必须存在

    eng = bootstrap.create_engine()
    assert isinstance(eng, MujocoEngine)
    result = run_closed_loop(
        eng,
        model_ref="default",
        physics={"friction": 0.3, "joint_damping": 1.0},
        joint_targets=[0.5, -0.4],
    )
    assert result["ok"] and result["moved"], result

    with urllib.request.urlopen("http://127.0.0.1:8501", timeout=8) as resp:
        assert resp.status == 200

    print("PHASE2_ACCEPTANCE_PASS")


if __name__ == "__main__":
    main()
