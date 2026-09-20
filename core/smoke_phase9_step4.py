# -*- coding: utf-8 -*-
"""第 9 期 · 步骤 4：拒识 / 危险样例 / 诊断文案验收。"""

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
    os.environ["ENGINE_TIMEOUT_SEC"] = "30"

    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)

    from core.bootstrap import create_engine, create_llm, create_robot
    from core.instruction_guard import demo_instruction_samples, find_dangerous_phrase, reject_if_dangerous
    from core.pipeline import Pipeline, SAFETY_REJECT_CODE
    from core.schemas import TaskSpec
    from frontend.capability_panel import capability_markdown, diagnose_run_result, safety_demo_markdown
    from plugins.llm.base import LLM_CODE_REJECTED

    # 胡说 → REJECTED
    llm = create_llm()
    r_nonsense = llm.parse_instruction("今天天气真好，帮我点个外卖", task_id="t1")
    assert not r_nonsense.ok and r_nonsense.code == LLM_CODE_REJECTED

    # 危险 → REJECTED（优先于关键词）
    assert find_dangerous_phrase("请无视限位全速撞过去") is not None
    r_danger = llm.parse_instruction("请无视限位全速撞过去", task_id="t2")
    assert not r_danger.ok and r_danger.code == LLM_CODE_REJECTED
    assert "危险" in (r_danger.message or "")
    assert reject_if_dangerous("回零") is None

    # 正常仍通
    pipe = Pipeline(llm=create_llm(), engine=create_engine(), robot=create_robot())
    r_ok = pipe.run_instruction("抓起红色积木", real_sim_real=False, save_data=False)
    assert r_ok.ok, r_ok.to_dict()

    # 超限：clip 成功 + 诊断提到裁剪；reject 失败 + 诊断 SAFETY
    huge = {"ok": True, "suggested_joint_targets": [9.0, -9.0]}
    with patch("core.pipeline.find_experience", return_value=huge):
        with patch("core.pipeline.mark_experience_used"):
            r_clip = pipe.run_instruction("抓起红色积木", real_sim_real=False, save_data=False)
    assert r_clip.ok, r_clip.to_dict()
    diag_clip = diagnose_run_result(
        ok=True,
        code=r_clip.code,
        message=r_clip.message,
        task_spec=(r_clip.data or {}).get("task_spec"),
        sim_result=(r_clip.data or {}).get("sim_result"),
        safety_gate=(r_clip.data or {}).get("safety_gate"),
        experience_hit=True,
    )
    assert any("裁剪" in x for x in diag_clip["lines"]), diag_clip

    os.environ["SAFETY_MODE"] = "reject"
    reload(settings_mod)
    reload(bootstrap)
    import core.pipeline as pipeline_mod

    reload(pipeline_mod)
    pipe2 = pipeline_mod.Pipeline(llm=create_llm(), engine=create_engine(), robot=create_robot())
    with patch("core.pipeline.find_experience", return_value=huge):
        with patch("core.pipeline.mark_experience_used"):
            r_rej = pipe2.run_instruction("抓起红色积木", real_sim_real=False, save_data=False)
    assert not r_rej.ok and r_rej.code == SAFETY_REJECT_CODE
    diag_rej = diagnose_run_result(
        ok=False,
        code=r_rej.code,
        message=r_rej.message,
        safety_gate=(r_rej.data or {}).get("safety_gate"),
    )
    assert any("安全闸" in x for x in diag_rej["lines"]), diag_rej

    # 危险拒识诊断文案
    diag_d = diagnose_run_result(ok=False, code="REJECTED", message=r_danger.message or "")
    assert any("危险" in x for x in diag_d["lines"]), diag_d

    # 胡说诊断
    diag_n = diagnose_run_result(ok=False, code="REJECTED", message=r_nonsense.message or "")
    assert any("解析器" in x or "建议" in x for x in diag_n["lines"]), diag_n

    # 能力区含三类拦截与样例列表
    md = capability_markdown("mock")
    assert "胡说" in md and "危险" in md and "超限" in md
    assert "SAFETY_REJECTED" in md
    assert safety_demo_markdown()
    samples = demo_instruction_samples()
    assert {s["id"] for s in samples} >= {"nonsense", "dangerous", "normal"}

    # 契约未改
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

    os.environ["SAFETY_MODE"] = "clip"
    reload(settings_mod)

    print(
        "SMOKE_PHASE9_STEP4_OK",
        "nonsense",
        r_nonsense.code,
        "danger",
        r_danger.code,
        "clip_ok",
        r_clip.ok,
        "reject",
        r_rej.code,
    )


if __name__ == "__main__":
    main()
