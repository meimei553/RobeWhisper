# -*- coding: utf-8 -*-
"""阶段 6 · 步骤 3：Pipeline 接入 RSR 验收。"""

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

    pipe = Pipeline(llm=create_llm(), engine=create_engine(), robot=create_robot())

    # 默认关：结果中无 rsr 或不应自动校准
    r0 = pipe.run_instruction("回零", real_sim_real=False)
    assert r0.ok
    assert "rsr" not in (r0.data or {})

    # 显式开启：应有 rsr 且写回
    eng = create_engine()
    pipe2 = Pipeline(llm=create_llm(), engine=eng, robot=create_robot())
    before = eng.list_physics_params()
    r1 = pipe2.run_instruction("把红色杯子拿起来", real_sim_real=True)
    assert r1.ok, r1.to_dict()
    rsr = (r1.data or {}).get("rsr") or {}
    assert rsr.get("ok") is True
    assert rsr.get("reference_source") in {"pseudo_real", "robot"}
    assert "deviation" in rsr and "calibration" in rsr
    after = eng.list_physics_params()
    # 伪对照通常会触发更新
    assert rsr["calibration"].get("updated") is True
    assert abs(float(after["joint_damping"]) - float(before["joint_damping"])) > 1e-9 or abs(
        float(after["friction"]) - float(before["friction"])
    ) > 1e-9

    # 配置默认关时 create_pipeline 行为与阶段4兼容
    os.environ["USE_REAL_SIM_REAL"] = "false"
    reload(settings_mod)
    reload(bootstrap)
    r2 = bootstrap.create_pipeline().run_instruction("回零")
    assert r2.ok and "rsr" not in (r2.data or {})

    print("SMOKE_PHASE6_STEP3_OK", "src", rsr.get("reference_source"), "mae", rsr.get("deviation", {}).get("mae"))


if __name__ == "__main__":
    main()
