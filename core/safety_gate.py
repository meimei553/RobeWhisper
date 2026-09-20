# -*- coding: utf-8 -*-
"""
安全闸（第 9 期 · 步骤 1）

纯函数：根据关节限位裁剪或拒绝 TaskSpec 中的 joint_targets。
不修改 TaskSpec 主字段名；保留原始目标，便于第 11 期真机对照。

模式：
- clip：超限裁剪到边界后放行
- reject：任一关节超限则拒绝执行
"""

from __future__ import annotations

from typing import Any

from core.schemas import TaskSpec

# 无模型范围时的通用默认（弧度）；有模型时应传入真实 range
DEFAULT_JOINT_LIMITS: list[tuple[float, float]] = [(-2.8, 2.8), (-2.5, 2.5)]

SAFETY_MODE_CLIP = "clip"
SAFETY_MODE_REJECT = "reject"


def _as_task_dict(task: TaskSpec | dict[str, Any]) -> dict[str, Any]:
    if isinstance(task, TaskSpec):
        return task.to_dict()
    return dict(task or {})


def resolve_safety_mode(task_dict: dict[str, Any], override: str | None = None) -> str:
    """优先级：显式 override > constraints.safety_mode > params.safety_mode > clip。"""
    if override:
        mode = str(override).strip().lower()
    else:
        cons = task_dict.get("constraints") or {}
        params = task_dict.get("params") or {}
        mode = str(cons.get("safety_mode") or params.get("safety_mode") or SAFETY_MODE_CLIP).strip().lower()
    if mode not in {SAFETY_MODE_CLIP, SAFETY_MODE_REJECT}:
        return SAFETY_MODE_CLIP
    return mode


def resolve_joint_limits(
    task_dict: dict[str, Any],
    joint_limits: list[tuple[float, float]] | None = None,
) -> list[tuple[float, float]]:
    """
    限位来源：参数传入 > constraints.joint_limits > 默认。
    joint_limits 形如 [[lo, hi], ...] 或 [(lo, hi), ...]
    """
    if joint_limits:
        return [(float(a), float(b)) for a, b in joint_limits]
    cons = task_dict.get("constraints") or {}
    raw = cons.get("joint_limits")
    if isinstance(raw, list) and raw:
        out: list[tuple[float, float]] = []
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                out.append((float(item[0]), float(item[1])))
        if out:
            return out
    return list(DEFAULT_JOINT_LIMITS)


def extract_joint_targets(task_dict: dict[str, Any]) -> list[float] | None:
    params = task_dict.get("params") or {}
    raw = params.get("joint_targets")
    if raw is None:
        return None
    if not isinstance(raw, list) or not raw:
        return None
    return [float(x) for x in raw]


def apply_safety_gate(
    task: TaskSpec | dict[str, Any],
    *,
    joint_limits: list[tuple[float, float]] | None = None,
    mode: str | None = None,
) -> dict[str, Any]:
    """
    对任务单做安全闸检查。

    返回：
      ok: 是否允许继续执行
      mode: clip | reject
      skipped: 无 joint_targets 时为 True（不拦，留给示意动作路径）
      original_targets / applied_targets
      violations: [{index, value, lo, hi}, ...]
      message: 中文说明
      # 不堵死后续：附带可写入 params 的旁路信息
      safety_audit: {clipped: bool, ...}
    """
    data = _as_task_dict(task)
    resolved_mode = resolve_safety_mode(data, mode)
    limits = resolve_joint_limits(data, joint_limits)
    original = extract_joint_targets(data)

    if original is None:
        return {
            "ok": True,
            "mode": resolved_mode,
            "skipped": True,
            "original_targets": None,
            "applied_targets": None,
            "violations": [],
            "message": "无 joint_targets，跳过关节限位闸（示意动作路径仍可用）",
            "safety_audit": {"clipped": False, "rejected": False, "skipped": True},
        }

    violations: list[dict[str, Any]] = []
    applied: list[float] = []
    for i, val in enumerate(original):
        if i < len(limits):
            lo, hi = limits[i]
        else:
            lo, hi = DEFAULT_JOINT_LIMITS[-1]
        if val < lo or val > hi:
            violations.append({"index": i, "value": val, "lo": lo, "hi": hi})
        applied.append(min(hi, max(lo, val)))

    if not violations:
        return {
            "ok": True,
            "mode": resolved_mode,
            "skipped": False,
            "original_targets": original,
            "applied_targets": list(original),
            "violations": [],
            "message": "关节目标在限位内，安全闸放行",
            "safety_audit": {"clipped": False, "rejected": False, "skipped": False},
        }

    if resolved_mode == SAFETY_MODE_REJECT:
        detail = "；".join(
            f"关节{v['index']}: {v['value']:.4f} 超出 [{v['lo']:.4f}, {v['hi']:.4f}]" for v in violations
        )
        return {
            "ok": False,
            "mode": resolved_mode,
            "skipped": False,
            "original_targets": original,
            "applied_targets": None,
            "violations": violations,
            "message": f"安全闸拒绝：关节目标超限。{detail}",
            "safety_audit": {
                "clipped": False,
                "rejected": True,
                "skipped": False,
                "original_targets": original,
            },
        }

    # clip
    detail = "；".join(
        f"关节{v['index']}: {v['value']:.4f}→[{v['lo']:.4f},{v['hi']:.4f}]" for v in violations
    )
    return {
        "ok": True,
        "mode": resolved_mode,
        "skipped": False,
        "original_targets": original,
        "applied_targets": applied,
        "violations": violations,
        "message": f"安全闸已裁剪超限关节目标。{detail}",
        "safety_audit": {
            "clipped": True,
            "rejected": False,
            "skipped": False,
            "original_targets": original,
            "applied_targets": applied,
        },
    }


def merge_gate_into_params(params: dict[str, Any] | None, gate: dict[str, Any]) -> dict[str, Any]:
    """
    将闸结果合并进 params（只增不改主契约字段）。
    若 clip 且有 applied_targets，写入 joint_targets，并保留 joint_targets_original。
    """
    out = dict(params or {})
    audit = dict(gate.get("safety_audit") or {})
    if gate.get("original_targets") is not None:
        out["joint_targets_original"] = list(gate["original_targets"])
    if gate.get("ok") and gate.get("applied_targets") is not None and not gate.get("skipped"):
        out["joint_targets"] = list(gate["applied_targets"])
    out["safety_audit"] = audit
    out["safety_message"] = str(gate.get("message") or "")
    return out
