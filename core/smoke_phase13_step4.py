# -*- coding: utf-8 -*-
"""第 13 期 · 步骤 4：网站能力区与演示样例。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from frontend.capability_panel import (
        contact_scene_status_hint,
        feature_catalog_items,
        feature_catalog_markdown,
    )

    items = feature_catalog_items()
    ids = [x["id"] for x in items]
    assert "contact_trial" in ids
    contact = next(x for x in items if x["id"] == "contact_trial")
    assert "不是工业" in contact["what"] or "不代表" in contact["what"]
    assert "接触试机场景" in contact["how"] or "模型" in contact["how"]

    md = feature_catalog_markdown()
    assert "接触试机" in md
    assert "默认" in md

    off = contact_scene_status_hint("default")
    assert "关" in off["label"] or "无物体" in off["label"]
    on = contact_scene_status_hint("builtin_arm2_contact")
    assert "已开" in on["label"] or "接触场景" in on["label"]
    assert "夹稳" in on["detail"] or "抓住" in on["detail"]

    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    assert "切换到接触试机场景并抓一次" in app
    assert "恢复默认臂（无物体）" in app
    assert "contact_scene_status_hint" in app
    assert "demo_contact_grab_btn" in app

    demo = (_ROOT / "core" / "演示剧本.txt").read_text(encoding="utf-8")
    assert "接触试机" in demo
    assert "切换到接触试机场景" in demo or "接触试机场景" in demo

    # 默认仍是无物体臂
    from config import settings

    assert settings.DEFAULT_MODEL_REL.replace("\\", "/") == "builtin_arm2/model.xml"

    print("SMOKE_PHASE13_STEP4_OK")


if __name__ == "__main__":
    main()
