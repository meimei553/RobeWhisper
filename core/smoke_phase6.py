# -*- coding: utf-8 -*-
"""阶段 6 总复验。用法：python -m core.smoke_phase6"""

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
    os.environ["USE_REAL_SIM_REAL"] = "false"
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)

    from config import settings
    from core.bootstrap import create_engine, create_llm, create_pipeline, create_robot
    from core.pipeline import Pipeline
    from core.schemas import TaskSpec

    # 配置契约
    assert hasattr(settings, "USE_REAL_SIM_REAL")
    assert hasattr(settings, "RSR_CALIB_GAIN")
    assert bool(settings.USE_REAL_SIM_REAL) is False

    # 模块落盘
    for rel in (
        "core/trajectory_metrics.py",
        "core/param_calibrator.py",
        "core/rsr_loop.py",
        "core/smoke_phase6_step1.py",
        "core/smoke_phase6_step2.py",
        "core/smoke_phase6_step3.py",
        "core/smoke_phase6_step4.py",
    ):
        assert (_ROOT / rel).exists(), rel

    # 默认关：与阶段3–5兼容
    pipe = create_pipeline()
    off = pipe.run_instruction("回零")
    assert off.ok
    assert "rsr" not in (off.data or {})

    # 显式开：偏差 + 写回
    eng = create_engine()
    before = eng.list_physics_params()
    on = Pipeline(llm=create_llm(), engine=eng, robot=create_robot()).run_instruction(
        "把红色杯子拿起来",
        real_sim_real=True,
    )
    assert on.ok
    rsr = (on.data or {}).get("rsr") or {}
    assert rsr.get("ok") is True
    assert rsr.get("reference_source") in {"pseudo_real", "robot"}
    assert (rsr.get("deviation") or {}).get("mae") is not None
    assert (rsr.get("calibration") or {}).get("updated") is True
    after = eng.list_physics_params()
    assert after["friction"] != before["friction"] or after["joint_damping"] != before["joint_damping"]

    # 网站接线
    app = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    assert "Real-Sim-Real 校准摘要" in app
    assert "rsr_enable_ui" in app
    assert "real_sim_real=" in app
    assert "last_rsr" in app

    # TaskSpec 主字段未改
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

    print(
        "PHASE6_ACCEPTANCE_PASS",
        "site",
        site,
        "mae",
        (rsr.get("deviation") or {}).get("mae"),
    )


if __name__ == "__main__":
    main()
