# -*- coding: utf-8 -*-
"""阶段4·步骤2：仅验收经验库存取。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from core.experience_store import find_experience, list_experiences, remember_experience
    from core.schemas import TaskSpec

    remember_experience(
        action="grab",
        target="red_cup",
        raw_text="拿红杯",
        trajectory=[{"t": 1, "joint_positions": [0.5, -0.3]}],
        ok=True,
        params={"steps": 3},
    )
    hit = find_experience("grab", "red_cup")
    assert hit and hit.get("ok") is True
    assert hit.get("suggested_joint_targets") == [0.5, -0.3]

    remember_experience(
        action="grab",
        target="red_cup",
        raw_text="失败尝试",
        trajectory=[],
        ok=False,
        reason="test_fail",
    )
    # 失败不应覆盖成功经验
    hit2 = find_experience("grab", "red_cup")
    assert hit2 and hit2.get("ok") is True

    assert list_experiences(5)
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
    print("SMOKE_PHASE4_STEP2_OK", hit2.get("key"))


if __name__ == "__main__":
    main()
