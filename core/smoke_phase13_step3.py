# -*- coding: utf-8 -*-
"""第 13 期 · 步骤 3：诊断 / 回复 / 实验落盘含接触试机。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from core.contact_scene_contract import (
        format_contact_trial_message,
        grasp_proxy_label,
    )
    from core.schemas import TaskSpec
    from frontend.capability_panel import diagnose_run_result
    from frontend.reply_text import format_success_reply
    from plugins.engines.mujoco_engine import MujocoEngine

    assert "关节示意" in grasp_proxy_label("no_scene")
    assert "不是工业" in grasp_proxy_label("ok") or "夹稳" in grasp_proxy_label("ok")

    # 默认臂：诊断含「无试机物体」
    eng = MujocoEngine()
    eng.load("default")
    sim0 = eng.run_task(TaskSpec(task_id="d0", action="grab", target="cup")).to_dict()
    diag0 = diagnose_run_result(
        ok=True,
        code="OK",
        message="ok",
        task_spec={"action": "grab", "target": "cup"},
        sim_result=sim0,
        use_real_robot=False,
    )
    blob0 = "\n".join(diag0.get("lines") or [])
    assert "接触试机" in blob0
    assert "无试机物体" in blob0 or "关节示意" in blob0

    msg0 = format_contact_trial_message(sim0.get("metrics") or {})
    assert "关节示意" in msg0 or "无试机物体" in msg0

    reply0 = format_success_reply(
        "ok",
        action="grab",
        target="cup",
        frame_count=3,
        experience_hit=False,
        experiment_id="e1",
        robot_name="mock",
        robot_msg="",
        rsr_msg="未执行",
        contact_msg=msg0,
    )
    assert "接触试机：" in reply0

    # 接触场景：诊断能看出代理结果
    eng.load("builtin_arm2_contact")
    sim1 = eng.run_task(
        TaskSpec(task_id="d1", action="grab", target="block", params={"steps": 6})
    ).to_dict()
    diag1 = diagnose_run_result(
        ok=True,
        code="OK",
        message="ok",
        task_spec={"action": "grab", "target": "block"},
        sim_result=sim1,
        use_real_robot=False,
    )
    blob1 = "\n".join(diag1.get("lines") or [])
    assert "接触试机" in blob1
    assert "无试机物体" not in blob1
    assert any(
        x in blob1 for x in ("代理通过", "未检测", "不确定", "接近", "接触")
    )

    # Pipeline 落盘含 grasp_proxy
    from core.bootstrap import create_llm, create_robot
    from core.pipeline import Pipeline

    pipe = Pipeline(llm=create_llm(), engine=MujocoEngine(), robot=create_robot())
    out = pipe.run_instruction("抓起红色积木", model_ref="default")
    assert out.ok, out.to_dict()
    sim_m = ((out.data or {}).get("sim_result") or {}).get("metrics") or {}
    assert sim_m.get("grasp_proxy") == "no_scene"
    exp = (out.data or {}).get("experiment") or {}
    # 实验 JSON 路径可读
    path = exp.get("path") or ""
    if path:
        raw = Path(path).read_text(encoding="utf-8")
        assert "grasp_proxy" in raw
        assert "no_scene" in raw

    # 网站已接入 contact_msg
    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    assert "format_contact_trial_message" in app
    assert "contact_msg" in app

    print("SMOKE_PHASE13_STEP3_OK")


if __name__ == "__main__":
    main()
