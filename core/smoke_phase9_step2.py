# -*- coding: utf-8 -*-
"""第 9 期 · 步骤 2：安全闸接入 Pipeline 验收。"""

from __future__ import annotations

import os
import sys
from importlib import reload
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    os.environ["ENGINE_BACKEND"] = "mujoco"
    os.environ["LLM_BACKEND"] = "mock"
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    os.environ["USE_REAL_SIM_REAL"] = "false"
    os.environ["SAFETY_MODE"] = "clip"
    import config.settings as settings_mod
    import core.bootstrap as bootstrap
    import core.pipeline as pipeline_mod

    reload(settings_mod)
    reload(bootstrap)
    reload(pipeline_mod)

    from core.bootstrap import create_engine, create_llm, create_robot
    from core.pipeline import Pipeline, SAFETY_REJECT_CODE
    from core.schemas import TaskSpec
    from core.safety_gate import apply_safety_gate, merge_gate_into_params

    pipe = Pipeline(llm=create_llm(), engine=create_engine(), robot=create_robot())

    # 正常指令仍通；屏蔽经验以免「回零」被历史注入 joint_targets
    # （真实库里常有 home 经验，闸会放行而非 skip——属正常，不是漏洞）
    with patch("core.pipeline.find_experience", return_value=None):
        r0 = pipe.run_instruction("回零", real_sim_real=False)
    assert r0.ok, r0.to_dict()
    assert "safety_gate" in (r0.data or {})
    assert (r0.data or {})["safety_gate"].get("skipped") is True

    # clip：经验注入超限目标 → 应成功且已裁剪
    huge = {"ok": True, "suggested_joint_targets": [9.0, -9.0]}
    with patch("core.pipeline.find_experience", return_value=huge):
        with patch("core.pipeline.mark_experience_used"):
            r1 = pipe.run_instruction("抓起红色积木", real_sim_real=False)
    assert r1.ok, r1.to_dict()
    gate1 = (r1.data or {}).get("safety_gate") or {}
    assert gate1.get("safety_audit", {}).get("clipped") is True
    applied = gate1.get("applied_targets") or []
    assert applied[0] <= 2.8 + 1e-6
    assert applied[1] >= -2.5 - 1e-6
    # 原始意图仍保留（不堵死第11期对照）
    params = ((r1.data or {}).get("task_spec") or {}).get("params") or {}
    assert params.get("joint_targets_original") == [9.0, -9.0]

    # reject：超限应失败
    os.environ["SAFETY_MODE"] = "reject"
    reload(settings_mod)
    reload(bootstrap)
    reload(pipeline_mod)
    pipe2 = Pipeline(llm=create_llm(), engine=create_engine(), robot=create_robot())
    with patch("core.pipeline.find_experience", return_value=huge):
        with patch("core.pipeline.mark_experience_used"):
            r2 = pipe2.run_instruction("抓起红色积木", real_sim_real=False)
    assert not r2.ok
    assert r2.code == SAFETY_REJECT_CODE
    assert "safety_gate" in (r2.data or {})

    # 引擎限位可读；契约未改
    eng = create_engine()
    eng.load("default")
    limits = eng.get_joint_limits()
    assert len(limits) >= 2
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

    # 恢复 clip，避免污染后续
    os.environ["SAFETY_MODE"] = "clip"
    reload(settings_mod)

    print("SMOKE_PHASE9_STEP2_OK", "clip_applied", applied, "reject", r2.code)


if __name__ == "__main__":
    main()
