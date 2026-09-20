# -*- coding: utf-8 -*-
"""
阶段 2 仿真网站闭环工作流（与前端同一顺序，供验收脚本复用）。

顺序：选模型 → 写物理参数 → 关节步进 → 读状态
"""

from __future__ import annotations

from typing import Any

from core.model_catalog import list_model_options
from plugins.engines.base import BaseEngine


def run_closed_loop(
    engine: BaseEngine,
    *,
    model_ref: str = "default",
    physics: dict[str, Any] | None = None,
    joint_targets: list[float] | None = None,
    nsub: int = 40,
) -> dict[str, Any]:
    """
    执行一次完整闭环，返回结构化结果（不含 Streamlit）。

    失败时 ok=False，message 为友好说明，不抛给调用方堆栈。
    """
    try:
        options = list_model_options()
        refs = {o["ref"] for o in options}
        # default 总是允许；其它 ref 若扫描不到仍尝试 load（可能是刚上传）
        engine.load(model_ref)
        engine.reset()

        phys_before = engine.list_physics_params()
        phys_after = phys_before
        if physics:
            phys_after = engine.set_physics_params(physics)

        before = engine.get_state()
        targets = joint_targets
        if targets is None:
            jp = list(before.get("joint_positions") or [])
            targets = [0.5, -0.4][: max(1, len(jp))]
            while len(targets) < len(jp):
                targets.append(0.0)

        after = engine.step(
            {
                "action": "move",
                "joint_targets": targets,
                "nsub": nsub,
            }
        )
        moved = False
        b = before.get("joint_positions") or []
        a = after.get("joint_positions") or []
        if b and a:
            moved = sum(abs(float(x) - float(y)) for x, y in zip(b, a)) > 1e-3

        return {
            "ok": True,
            "message": "闭环完成",
            "model_ref": model_ref,
            "available_refs_sample": sorted(list(refs))[:8],
            "physics_before": phys_before,
            "physics_after": phys_after,
            "state_before": before,
            "state_after": after,
            "moved": moved,
        }
    except Exception:
        return {
            "ok": False,
            "message": "思考遇到一些阻碍，请稍后再试。",
            "model_ref": model_ref,
            "moved": False,
        }
