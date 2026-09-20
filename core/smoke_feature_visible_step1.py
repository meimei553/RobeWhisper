# -*- coding: utf-8 -*-
"""能力可见 · 步骤1：可选能力清单一眼可见。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from frontend.capability_panel import feature_catalog_items, feature_catalog_markdown

    items = feature_catalog_items()
    assert len(items) >= 3
    ids = [x["id"] for x in items]
    assert ids[:3] == ["real_robot", "rsr", "cloud_api"]
    assert "contact_trial" in ids
    assert "multi_step" in ids

    for it in items:
        assert it.get("title")
        assert it.get("what")
        assert "默认" in it.get("default", "")
        how = it.get("how", "")
        assert (
            ".env" in how
            or "勾选" in how
            or "模型" in how
            or "接触" in how
            or "样例" in how
            or "先" in how
            or "多步" in how
        )

    md = feature_catalog_markdown()
    assert "可选能力一览" in md
    assert "真机发送" in md
    assert "RSR" in md or "虚实校准" in md
    assert "云端语言 API" in md or "API" in md
    assert "接触试机" in md
    # 关着也能看见：文案强调默认关 / 功能在
    assert "默认" in md
    assert "USE_REAL_ROBOT" in md
    assert "LLM_BACKEND" in md
    assert "USE_REAL_SIM_REAL" in md or "Real-Sim-Real" in md

    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    assert "feature_catalog_markdown" in app

    # 主字段未改（红线抽检）
    from core.schemas import TaskSpec

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

    print("SMOKE_FEATURE_VISIBLE_STEP1_OK")


if __name__ == "__main__":
    main()
