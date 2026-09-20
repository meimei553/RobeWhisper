# -*- coding: utf-8 -*-
"""能力可见 · 步骤4：RSR 状态提示加固。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from frontend.capability_panel import (
        build_rsr_status_hint,
        diagnose_run_result,
        format_rsr_run_message,
        format_rsr_status_line,
        rsr_reference_source_label,
    )

    assert rsr_reference_source_label("pseudo_real") == "伪对照"
    assert rsr_reference_source_label("robot") == "真轨迹"

    off = build_rsr_status_hint(rsr_enabled=False, last_rsr=None)
    assert off["mode"] == "off"
    assert "不会做校准" in off["label"] or "不会做校准" in off["detail"]
    assert "不会做校准" in format_rsr_status_line(off)

    waiting = build_rsr_status_hint(rsr_enabled=True, last_rsr=None)
    assert waiting["mode"] == "waiting"
    assert "尚未执行" in waiting["label"]

    pseudo = build_rsr_status_hint(
        rsr_enabled=True,
        last_rsr={
            "ok": True,
            "reference_source": "pseudo_real",
            "deviation": {"mae": 0.12},
            "message": "ok",
        },
    )
    assert pseudo["mode"] == "pseudo"
    assert "伪对照" in pseudo["label"]
    assert "真机回流" in pseudo["detail"] or "假对照" in pseudo["detail"]

    real = build_rsr_status_hint(
        rsr_enabled=True,
        last_rsr={"ok": True, "reference_source": "robot", "deviation": {"mae": 0.01}},
    )
    assert real["mode"] == "real"
    assert "真轨迹" in real["label"]

    msg = format_rsr_run_message(
        {"ok": True, "reference_source": "pseudo_real", "deviation": {"mae": 0.2}},
        enabled=True,
    )
    assert "伪对照" in msg
    assert "pseudo_real" not in msg  # 聊天一句用人话，不甩代码名

    off_msg = format_rsr_run_message(None, enabled=False)
    assert "不会做校准" in off_msg or "关" in off_msg

    diag = diagnose_run_result(
        ok=True,
        code="OK",
        message="ok",
        task_spec={"action": "grab", "target": "red_block"},
        sim_result={"trajectory": [{"t": 0, "joint_positions": [0.0]}]},
        rsr={"ok": True, "reference_source": "pseudo_real", "deviation": {"mae": 0.1}},
        use_real_robot=False,
    )
    blob = "\n".join(diag.get("lines") or [])
    assert "伪对照" in blob
    assert "第12期" in blob or "真轨迹" in blob

    diag_off = diagnose_run_result(
        ok=True,
        code="OK",
        message="ok",
        task_spec={"action": "grab", "target": "cup"},
        sim_result={"trajectory": [{"t": 0, "joint_positions": [0.0]}]},
        rsr=None,
        use_real_robot=False,
    )
    assert any("不会做校准" in x or "未执行" in x for x in (diag_off.get("lines") or []))

    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    assert "build_rsr_status_hint" in app
    assert "format_rsr_status_line" in app
    # 不写死伪对照为唯一终局
    assert "第12期" in app or "真轨迹" in app

    # 核心回流仍允许伪对照（未堵死第12期替换口）
    rsr_src = (_ROOT / "core" / "rsr_loop.py").read_text(encoding="utf-8")
    assert "allow_pseudo_real" in rsr_src
    assert "pseudo_real" in rsr_src
    assert 'source = "robot"' in rsr_src or 'source = "robot"' in rsr_src.replace("'", '"')

    print("SMOKE_FEATURE_VISIBLE_STEP4_OK")


if __name__ == "__main__":
    main()
