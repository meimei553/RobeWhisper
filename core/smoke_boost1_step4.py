# -*- coding: utf-8 -*-
"""补强包一 · 步骤 4：网站说明与演示剧本。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from core.pose_grounding_contract import (
        build_proxy_summary,
        format_proxy_summary_lines,
    )
    from frontend.capability_panel import (
        capability_markdown,
        contact_scene_status_hint,
        feature_catalog_items,
        feature_catalog_markdown,
    )

    contact = next(x for x in feature_catalog_items() if x["id"] == "contact_trial")
    blob = contact["what"] + contact["how"] + contact["default"]
    assert "相机" in blob
    assert "抓住" in blob
    assert "看见杯子" not in blob
    assert "已经抓住" not in blob
    assert "标定完成" not in blob

    md = feature_catalog_markdown()
    assert "不是相机" in md or "相机" in md
    assert "代理摘要" in md or "场景位姿" in md

    cap = capability_markdown("mock")
    assert "场景位姿" in cap
    assert "不是相机" in cap
    assert "已经抓住" not in cap
    assert "标定完成" not in cap

    off = contact_scene_status_hint("default")
    assert "相机" in off["detail"] or "关节示意" in off["detail"]
    on = contact_scene_status_hint("builtin_arm2_contact")
    assert "相机" in on["detail"]
    assert "抓住" in on["detail"]

    lines = format_proxy_summary_lines(
        build_proxy_summary(
            metrics={"pose_source": "scene_model", "grasp_proxy": "ok", "contact_scene": True},
            rsr={"reference_source": "pseudo_real"},
        )
    )
    joined = "\n".join(lines)
    assert "位姿来源" in joined
    assert "接触代理" in joined
    assert "相机" in joined
    assert "伪对照" in joined

    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    assert "本次试机代理摘要" in app
    assert "不是相机" in app
    assert "last_proxy_summary" in app
    assert "format_proxy_summary_lines" in app
    # 沿用旧按钮，不新开抓取大按钮
    assert "切换到接触试机场景并抓一次" in app
    assert "看见杯子" not in app
    assert "已经抓住" not in app
    assert "标定完成" not in app

    demo = (_ROOT / "core" / "演示剧本.txt").read_text(encoding="utf-8")
    assert "场景位姿示意" in demo
    assert "不是相机" in demo
    assert "代理摘要" in demo
    assert "看见杯子" in demo  # 剧本里作为「不要这么说」的检查项
    assert "已经抓住" in demo

    print("SMOKE_BOOST1_STEP4_OK")


if __name__ == "__main__":
    main()
