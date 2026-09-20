# -*- coding: utf-8 -*-
"""第 14 期 · 步骤 4：网站样例与诊断。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from core.instruction_guard import demo_instruction_samples
    from core.multi_step_contract import format_multi_step_message, multi_step_diagnosis_lines
    from frontend.capability_panel import (
        capability_markdown,
        diagnose_run_result,
        feature_catalog_items,
        feature_catalog_markdown,
    )
    from frontend.reply_text import format_success_reply

    items = feature_catalog_items()
    ids = [x["id"] for x in items]
    assert "multi_step" in ids
    assert "contact_trial" in ids

    md = feature_catalog_markdown()
    assert "多步试机" in md

    cap = capability_markdown("mock")
    assert "多步" in cap
    assert "wait" in cap or "等待" in cap

    samples = demo_instruction_samples()
    assert any(s["id"] == "multi_step" for s in samples)
    multi_s = next(s for s in samples if s["id"] == "multi_step")
    assert "先" in multi_s["text"] and "再" in multi_s["text"]

    msg = format_multi_step_message(
        {"steps": [{"action": "home"}, {"action": "grab", "target": "cup"}]},
        {"step_count": 2, "step_actions": ["home", "grab"]},
        None,
    )
    assert "2" in msg and "home" in msg

    diag = diagnose_run_result(
        ok=True,
        code="OK",
        message="已按序执行 2 步",
        task_spec={
            "action": "home",
            "target": "",
            "steps": [{"action": "home"}, {"action": "grab", "target": "red_cup"}],
        },
        sim_result={"trajectory": [{}, {}], "metrics": {"step_count": 2, "step_actions": ["home", "grab"], "multi_step": True}},
        multi_step={"step_count": 2, "step_actions": ["home", "grab"]},
        llm_backend="mock",
        use_real_robot=False,
    )
    joined = "\n".join(diag["lines"])
    assert "多步试机" in joined
    assert "params" in joined or "细分" in joined

    reply = format_success_reply(
        "已按序执行 2 步",
        action="home",
        target="",
        frame_count=4,
        experience_hit=False,
        experiment_id="e1",
        robot_name="mock_robot",
        robot_msg="",
        rsr_msg="关",
        multi_step_msg=msg,
    )
    assert "多步试机" in reply

    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    assert "多步样例" in app or "demo_sample_multi_step" in app or "multi_step" in app
    assert "format_multi_step_message" in app
    assert "先回零再抓" in app

    demo = (_ROOT / "core" / "演示剧本.txt").read_text(encoding="utf-8")
    assert "多步试机" in demo
    assert "先回零再抓" in demo or "多步样例" in demo

    print("SMOKE_PHASE14_STEP4_OK")


if __name__ == "__main__":
    main()
