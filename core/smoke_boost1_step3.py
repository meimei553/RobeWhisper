# -*- coding: utf-8 -*-
"""补强包一 · 步骤 3：诊断 / 落盘 / 代理摘要。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from core.bootstrap import create_llm, create_robot
    from core.contact_scene_contract import contact_reason_zh
    from core.pipeline import Pipeline
    from core.pose_grounding_contract import (
        format_pose_grounding_message,
        pose_grounding_diagnosis_lines,
        pose_source_label,
    )
    from core.schemas import TaskSpec
    from frontend.capability_panel import diagnose_run_result
    from frontend.reply_text import format_success_reply
    from plugins.engines.mujoco_engine import MujocoEngine

    assert "相机" in pose_source_label("scene_model") or "仿真" in pose_source_label("scene_model")
    assert "场景没开" in contact_reason_zh("no_scene")
    assert "够不着" in contact_reason_zh("no_contact")
    assert "抓住" in contact_reason_zh("ok") or "碰到" in contact_reason_zh("ok")

    mj = MujocoEngine()
    mj.load("default")
    sim0 = mj.run_task(TaskSpec(task_id="p0", action="grab", target="cup")).to_dict()
    msg0 = format_pose_grounding_message(sim0.get("metrics") or {})
    assert "关节示意" in msg0 or "无试机" in msg0 or "无场景" in msg0
    diag0 = diagnose_run_result(
        ok=True,
        code="OK",
        message="ok",
        task_spec={"action": "grab", "target": "cup"},
        sim_result=sim0,
        use_real_robot=False,
    )
    blob0 = "\n".join(diag0.get("lines") or [])
    assert "场景位姿示意" in blob0
    assert "相机" not in blob0 or "不是相机" in blob0 or "没有用场景" in blob0
    assert "原因：" in blob0 or "接触试机" in blob0

    mj.load("builtin_arm2_contact")
    sim1 = mj.run_task(TaskSpec(task_id="p1", action="grab", target="block", params={"steps": 6})).to_dict()
    lines1 = pose_grounding_diagnosis_lines(sim1.get("metrics") or {})
    joined1 = "\n".join(lines1)
    assert "场景位姿示意" in joined1
    assert "相机" in joined1
    assert "抓住" not in joined1 or "不代表" in joined1

    reply = format_success_reply(
        "ok",
        action="grab",
        target="block",
        frame_count=3,
        experience_hit=False,
        experiment_id="e",
        robot_name="mock",
        robot_msg="",
        rsr_msg="关",
        pose_msg=format_pose_grounding_message(sim1.get("metrics") or {}),
        contact_msg="x",
    )
    assert "场景位姿示意" in reply

    pipe = Pipeline(llm=create_llm(), engine=mj, robot=create_robot())
    r = pipe.run_instruction("抓起红色积木", model_ref="builtin_arm2_contact", real_sim_real=False, save_data=True)
    assert r.ok, r.to_dict()
    snap = (r.data or {}).get("run_snapshot") or {}
    extra = snap.get("extra") if isinstance(snap.get("extra"), dict) else {}
    assert extra.get("pose_source") in {"scene_model", "uncertain", "none"}
    summary = extra.get("proxy_summary") if isinstance(extra.get("proxy_summary"), dict) else {}
    assert "pose_source" in summary and "grasp_proxy" in summary
    exp = (r.data or {}).get("experiment") or {}
    path = exp.get("path") or ""
    if path:
        raw = Path(path).read_text(encoding="utf-8")
        assert "pose_source" in raw
        assert "proxy_summary" in raw

    from core.browse_tables import experiments_table_rows

    table = experiments_table_rows(8)
    assert table and "位姿来源" in table[0]

    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    assert "format_pose_grounding_message" in app
    assert "pose_msg" in app

    print("SMOKE_BOOST1_STEP3_OK")


if __name__ == "__main__":
    main()
