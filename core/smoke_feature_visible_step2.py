# -*- coding: utf-8 -*-
"""能力可见 · 步骤2：统一开闭状态条。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from frontend.capability_panel import (
        build_feature_switch_states,
        feature_catalog_markdown,
        format_feature_switch_line,
    )

    # 默认全关 → 三态均为 off
    off_rows = build_feature_switch_states(
        use_real_robot=False,
        robot_backend="mock",
        robot_endpoint="",
        robot_name="mock_robot",
        llm_backend_wanted="mock",
        llm_backend_effective="mock",
        llm_api_configured=False,
        use_rsr_config=False,
        rsr_ui=False,
    )
    assert [r["id"] for r in off_rows] == ["real_robot", "rsr", "cloud_api"]
    assert all(r["state"] == "off" for r in off_rows)
    assert all("关" in r["label"] for r in off_rows)

    # 真机：想开 http 但没填网址 → failed
    bad_robot = build_feature_switch_states(
        use_real_robot=True,
        robot_backend="http",
        robot_endpoint="",
        robot_name="mock_robot",
        llm_backend_wanted="mock",
        llm_backend_effective="mock",
        llm_api_configured=False,
        use_rsr_config=False,
        rsr_ui=False,
    )
    assert bad_robot[0]["state"] == "failed"
    assert "网址" in bad_robot[0]["reason"] or "ENDPOINT" in bad_robot[0]["reason"]

    # 真机：http 且实际是 HttpRobot → ready
    ok_robot = build_feature_switch_states(
        use_real_robot=True,
        robot_backend="http",
        robot_endpoint="http://127.0.0.1:9000/execute_task",
        robot_name="http_robot",
        llm_backend_wanted="mock",
        llm_backend_effective="mock",
        llm_api_configured=False,
        use_rsr_config=False,
        rsr_ui=False,
    )
    assert ok_robot[0]["state"] == "ready"

    # API：想开但未配齐 → failed，原因含缺项
    bad_api = build_feature_switch_states(
        use_real_robot=False,
        robot_backend="mock",
        robot_name="mock_robot",
        llm_backend_wanted="api",
        llm_backend_effective="mock",
        llm_api_configured=False,
        use_rsr_config=False,
        rsr_ui=False,
    )
    assert bad_api[2]["state"] == "failed"
    assert "回退" in bad_api[2]["reason"] or "缺" in bad_api[2]["reason"]

    # API：配齐且 effective=api → ready
    ok_api = build_feature_switch_states(
        use_real_robot=False,
        robot_backend="mock",
        robot_name="mock_robot",
        llm_backend_wanted="api",
        llm_backend_effective="api",
        llm_api_configured=True,
        use_rsr_config=False,
        rsr_ui=False,
    )
    assert ok_api[2]["state"] == "ready"

    # RSR：页面勾选 → ready
    rsr_on = build_feature_switch_states(
        use_real_robot=False,
        robot_backend="mock",
        robot_name="mock_robot",
        llm_backend_wanted="mock",
        llm_backend_effective="mock",
        llm_api_configured=False,
        use_rsr_config=False,
        rsr_ui=True,
    )
    assert rsr_on[1]["state"] == "ready"
    assert "勾选" in rsr_on[1]["reason"]

    line = format_feature_switch_line(bad_robot[0])
    assert "想开但未成功" in line

    # 清单文案已指向开闭状态（步骤1 勘误：去掉「后续才补状态条」的过时说明）
    md = feature_catalog_markdown()
    assert "开闭状态" in md

    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    assert "build_feature_switch_states" in app
    assert "开闭状态" in app

    print("SMOKE_FEATURE_VISIBLE_STEP2_OK")


if __name__ == "__main__":
    main()
