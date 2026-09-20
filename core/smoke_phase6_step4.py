# -*- coding: utf-8 -*-
"""阶段 6 · 步骤 4：网站展示 RSR 校准摘要验收。"""

from __future__ import annotations

import os
import sys
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    app = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    # 网站关键展示与接线
    assert "Real-Sim-Real 校准摘要" in app
    assert "rsr_enable_ui" in app
    assert "real_sim_real=" in app
    assert "last_rsr" in app
    assert '"rsr"' in app or "'rsr'" in app or "rsr_meta" in app
    assert "use_real_sim_real" in app
    assert "list_physics_params" in app

    os.environ["ENGINE_BACKEND"] = "mujoco"
    os.environ["LLM_BACKEND"] = "mock"
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    os.environ["USE_REAL_SIM_REAL"] = "false"
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)

    from core.bootstrap import create_engine, create_llm, create_robot
    from core.pipeline import Pipeline

    eng = create_engine()
    pipe = Pipeline(llm=create_llm(), engine=eng, robot=create_robot())

    # 关：与网站默认关一致，无 rsr 字段
    off = pipe.run_instruction("回零", real_sim_real=False)
    assert off.ok and "rsr" not in (off.data or {})

    # 开：网站勾选后应能拿到可展示字段
    on = pipe.run_instruction("把红色杯子拿起来", real_sim_real=True)
    assert on.ok
    rsr = (on.data or {}).get("rsr") or {}
    assert rsr.get("ok") is True
    assert "deviation" in rsr and "calibration" in rsr
    assert rsr["deviation"].get("mae") is not None
    assert "before" in (rsr.get("calibration") or {})
    assert "after" in (rsr.get("calibration") or {})
    # 引擎参数可读（网站摘要区会展示）
    params = eng.list_physics_params()
    assert "friction" in params and "joint_damping" in params

    print(
        "SMOKE_PHASE6_STEP4_OK",
        "mae",
        rsr["deviation"].get("mae"),
        "updated",
        rsr["calibration"].get("updated"),
    )


if __name__ == "__main__":
    main()
