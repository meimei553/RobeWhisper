# -*- coding: utf-8 -*-
"""
物理参数校准器（阶段 6 · 步骤 2）。

根据轨迹偏差标量，有界微调白名单参数：
- mae 偏大 → 略增阻尼、略调摩擦（启发式，非最优辨识）
- 所有更新夹紧在安全区间，避免仿真发散
"""

from __future__ import annotations

from typing import Any

# 允许调整的参数及边界
PARAM_BOUNDS: dict[str, tuple[float, float]] = {
    "friction": (0.05, 2.0),
    "joint_damping": (0.05, 5.0),
}

# 单次最大相对步长（相对当前值）
MAX_REL_STEP = 0.25
# 偏差较小时认为已收敛，不再改参
MAE_EPS = 1e-4


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def propose_param_updates(
    current_params: dict[str, Any],
    deviation: dict[str, Any],
    *,
    gain: float = 0.5,
) -> dict[str, Any]:
    """
    仅根据偏差提出新参数建议，不写引擎。

    返回：
      ok, updated(bool), before, after, message
    """
    before = {
        "friction": float(current_params.get("friction", 1.0)),
        "joint_damping": float(current_params.get("joint_damping", 0.5)),
    }
    if not deviation.get("ok"):
        return {
            "ok": False,
            "updated": False,
            "before": before,
            "after": dict(before),
            "message": str(deviation.get("message") or "偏差无效，跳过校准"),
        }

    mae = float(deviation.get("mae") or 0.0)
    if mae <= MAE_EPS:
        return {
            "ok": True,
            "updated": False,
            "before": before,
            "after": dict(before),
            "message": "偏差已足够小，无需调参",
            "mae": mae,
        }

    # 启发式：误差大 → 增阻尼抑制振荡；摩擦向中等值靠拢并略增以贴合接触
    damp = before["joint_damping"] * (1.0 + gain * min(mae, 1.0))
    fric = before["friction"] * (1.0 + 0.5 * gain * min(mae, 1.0))

    # 相对步长限制
    damp = _clamp(
        damp,
        before["joint_damping"] * (1.0 - MAX_REL_STEP),
        before["joint_damping"] * (1.0 + MAX_REL_STEP),
    )
    fric = _clamp(
        fric,
        before["friction"] * (1.0 - MAX_REL_STEP),
        before["friction"] * (1.0 + MAX_REL_STEP),
    )

    after = {
        "friction": _clamp(fric, *PARAM_BOUNDS["friction"]),
        "joint_damping": _clamp(damp, *PARAM_BOUNDS["joint_damping"]),
    }
    changed = any(abs(after[k] - before[k]) > 1e-9 for k in after)
    return {
        "ok": True,
        "updated": changed,
        "before": before,
        "after": after,
        "message": "已生成参数更新建议" if changed else "建议值与当前相同",
        "mae": mae,
    }


def apply_calibration_to_engine(engine: Any, deviation: dict[str, Any], *, gain: float = 0.5) -> dict[str, Any]:
    """
    读取引擎当前物理参数 → 提建议 → set_physics_params 写回。

    engine 需实现 list_physics_params / set_physics_params（BaseEngine）。
    """
    try:
        current = engine.list_physics_params()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "updated": False, "message": f"读取参数失败: {exc}"}

    proposal = propose_param_updates(current, deviation, gain=gain)
    if not proposal.get("ok") or not proposal.get("updated"):
        return proposal

    try:
        written = engine.set_physics_params(proposal["after"])
        after = {
            "friction": float(written.get("friction", proposal["after"]["friction"])),
            "joint_damping": float(written.get("joint_damping", proposal["after"]["joint_damping"])),
        }
        return {
            "ok": True,
            "updated": True,
            "before": proposal["before"],
            "after": after,
            "written": written,
            "mae": proposal.get("mae"),
            "message": "物理参数已写回引擎",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "updated": False,
            "before": proposal["before"],
            "after": proposal["after"],
            "message": f"写回失败: {exc}",
        }
