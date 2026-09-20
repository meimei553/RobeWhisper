# -*- coding: utf-8 -*-
"""第 9 期 · 步骤 1：安全闸纯函数验收。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from core.safety_gate import (
        SAFETY_MODE_CLIP,
        SAFETY_MODE_REJECT,
        apply_safety_gate,
        merge_gate_into_params,
    )
    from core.schemas import TaskSpec

    # 合法目标：放行
    ok_task = TaskSpec(
        task_id="t1",
        action="move",
        params={"joint_targets": [0.5, -0.5]},
    )
    g0 = apply_safety_gate(ok_task, mode=SAFETY_MODE_CLIP)
    assert g0["ok"] is True and not g0["violations"]
    assert g0["applied_targets"] == [0.5, -0.5]

    # 超限 + clip：裁剪后放行，保留 original
    over = TaskSpec(
        task_id="t2",
        action="move",
        params={"joint_targets": [9.0, -9.0]},
    )
    g1 = apply_safety_gate(over, mode=SAFETY_MODE_CLIP)
    assert g1["ok"] is True
    assert g1["original_targets"] == [9.0, -9.0]
    assert g1["applied_targets"][0] <= 2.8 + 1e-9
    assert g1["applied_targets"][1] >= -2.5 - 1e-9
    assert g1["safety_audit"]["clipped"] is True

    merged = merge_gate_into_params(over.params, g1)
    assert "joint_targets_original" in merged
    assert merged["joint_targets"] == g1["applied_targets"]

    # 超限 + reject：拒绝
    g2 = apply_safety_gate(over, mode=SAFETY_MODE_REJECT)
    assert g2["ok"] is False
    assert g2["applied_targets"] is None
    assert g2["safety_audit"]["rejected"] is True

    # 无 joint_targets：跳过，不堵示意路径（第13期前仍可用）
    bare = TaskSpec(task_id="t3", action="grab", target="red_block")
    g3 = apply_safety_gate(bare)
    assert g3["ok"] is True and g3["skipped"] is True

    # 契约主字段未改
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

    # 模块存在且不依赖 Streamlit
    assert (_ROOT / "core/safety_gate.py").exists()

    print(
        "SMOKE_PHASE9_STEP1_OK",
        "clip",
        g1["applied_targets"],
        "reject",
        g2["ok"],
        "skip",
        g3["skipped"],
    )


if __name__ == "__main__":
    main()
