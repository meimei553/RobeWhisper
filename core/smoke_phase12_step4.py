# -*- coding: utf-8 -*-
"""第 12 期 · 步骤 4：网站文案与真机清单对齐。"""

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
        feature_catalog_markdown,
        format_rsr_run_message,
        rsr_policy_label,
    )

    assert "严模式" in rsr_policy_label("require_real")
    assert "伪对照" in rsr_policy_label("prefer_real")

    off = build_rsr_status_hint(rsr_enabled=False)
    assert "不会做校准" in off["label"] or "不会做校准" in off["detail"]

    wait = build_rsr_status_hint(rsr_enabled=True, require_real_config=False)
    assert "伪对照" in wait["detail"] or "策略" in wait["detail"]

    strict_wait = build_rsr_status_hint(rsr_enabled=True, require_real_config=True)
    assert "严模式" in strict_wait["detail"] or "跳过" in strict_wait["detail"]

    pseudo = build_rsr_status_hint(
        rsr_enabled=True,
        last_rsr={
            "ok": True,
            "reference_source": "pseudo_real",
            "policy": "prefer_real",
            "reference_frame_count": 5,
            "deviation": {"mae": 0.1},
        },
    )
    assert pseudo["mode"] == "pseudo"
    assert "帧数" in pseudo["detail"] or "5" in pseudo["detail"]

    skipped = build_rsr_status_hint(
        rsr_enabled=True,
        last_rsr={
            "skipped": True,
            "ok": False,
            "policy": "require_real",
            "message": "无合格真机轨迹",
            "extract_reason": "关节维数不一致",
        },
    )
    assert skipped["mode"] == "skipped"
    assert "维数" in skipped["detail"] or "不合格" in skipped["detail"]

    msg = format_rsr_run_message(
        {
            "ok": True,
            "reference_source": "robot",
            "policy": "prefer_real",
            "reference_frame_count": 4,
            "deviation": {"mae": 0.01},
        },
        enabled=True,
    )
    assert "真轨迹" in msg and "帧数=4" in msg and "策略" in msg

    diag = diagnose_run_result(
        ok=True,
        code="OK",
        message="ok",
        task_spec={"action": "grab", "target": "cup"},
        sim_result={"trajectory": [{"t": 0, "joint_positions": [0.0]}]},
        rsr={
            "ok": True,
            "reference_source": "pseudo_real",
            "policy": "prefer_real",
            "reference_frame_count": 2,
            "deviation": {"mae": 0.2},
        },
    )
    blob = "\n".join(diag.get("lines") or [])
    assert "伪对照" in blob and ("策略" in blob or "默认" in blob)

    cat = feature_catalog_markdown()
    assert "--with-trajectory" in cat or "with-trajectory" in cat
    assert "RSR_REQUIRE_REAL_TRAJECTORY" in cat

    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    assert "rsr_policy_label" in app
    assert "require_real_config" in app
    assert "对照帧数" in app

    checklist = (_ROOT / "plugins" / "robot" / "真机联调检查清单.txt").read_text(encoding="utf-8")
    assert "--with-trajectory" in checklist
    assert "joint_positions" in checklist
    assert "RSR_REQUIRE_REAL_TRAJECTORY" in checklist
    assert "smoke_phase12_step4" in checklist

    print("SMOKE_PHASE12_STEP4_OK")


if __name__ == "__main__":
    main()
