# -*- coding: utf-8 -*-
"""
Real-Sim-Real 单次迭代（阶段 6 · 步骤 3；第 12 期步骤 1 加固提取）。

优先使用真机返回轨迹；若无合格真轨迹，则用「伪真机」对照轨迹（开发机可验收），
再调用偏差度量 + 参数校准写回引擎。

真轨迹最小帧约定（第 12 期）：
  [{"t": number, "joint_positions": [number, ...]}, ...]
  - 至少 1 帧；每帧 joint_positions 非空且维数一致；维数 ≤ 64
"""

from __future__ import annotations

from typing import Any

from core.param_calibrator import apply_calibration_to_engine
from core.trajectory_metrics import compute_trajectory_deviation, normalize_trajectory

# 可能出现的轨迹键名（只增别名，不改主契约）
_TRAJECTORY_KEYS = ("trajectory", "real_trajectory", "joint_trajectory")


def is_qualified_real_trajectory(
    frames: list[dict[str, Any]] | None,
) -> tuple[bool, list[dict[str, Any]], str]:
    """
    判断是否为合格真轨迹（形状检查，不看来源）。
    返回：(合格?, 清洗后的帧列表, 人话原因)
    """
    if not isinstance(frames, list):
        return False, [], "轨迹不是列表"
    if not frames:
        return False, [], "轨迹为空列表"

    clean = normalize_trajectory(frames)
    if not clean:
        return False, [], "无有效帧（需含 joint_positions）"

    lengths = [len(f.get("joint_positions") or []) for f in clean]
    if any(n <= 0 for n in lengths):
        return False, [], "存在空关节向量"
    if len(set(lengths)) != 1:
        return False, [], "关节维数不一致"
    if lengths[0] > 64:
        return False, [], "关节维数异常偏大（>64）"

    return True, clean, "合格"


def _iter_robot_result_containers(robot_result: dict[str, Any] | None) -> list[dict[str, Any]]:
    """
    按优先级收集可能藏轨迹的字典：
    data → data.ack → data.response → 顶层（兼容少见形状）
    """
    if not isinstance(robot_result, dict):
        return []
    out: list[dict[str, Any]] = []
    data = robot_result.get("data")
    if isinstance(data, dict):
        out.append(data)
        for nest_key in ("ack", "response"):
            nested = data.get(nest_key)
            if isinstance(nested, dict):
                out.append(nested)
    # 顶层兜底（极少见）
    out.append(robot_result)
    return out


def _raw_trajectory_from_container(container: dict[str, Any]) -> list[Any] | None:
    """从单个字典取原始轨迹列表；空 list / 非 list 视为没有。"""
    for key in _TRAJECTORY_KEYS:
        if key not in container:
            continue
        traj = container.get(key)
        if isinstance(traj, list) and traj:
            return traj
    return None


def extract_real_trajectory(robot_result: dict[str, Any] | None) -> list[dict[str, Any]]:
    """
    从 robot_result（ApiResult.to_dict）中提取合格真轨迹。
    不合格或缺失时返回 []（调用方再决定伪对照或 skip）。
    """
    for container in _iter_robot_result_containers(robot_result):
        raw = _raw_trajectory_from_container(container)
        if raw is None:
            continue
        ok, clean, _reason = is_qualified_real_trajectory(raw)
        if ok:
            return clean
        # 找到了键但不合格：继续找其它容器，全部失败则 []
    return []


def extract_real_trajectory_report(
    robot_result: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    提取过程报告（步骤1 验收/诊断用；不进 TaskSpec 主字段）。
    found_raw：是否看到过非空 list；qualified：是否最终合格。
    """
    seen_raw = False
    last_fail = ""
    for container in _iter_robot_result_containers(robot_result):
        raw = _raw_trajectory_from_container(container)
        if raw is None:
            continue
        seen_raw = True
        ok, clean, reason = is_qualified_real_trajectory(raw)
        if ok:
            return {
                "found_raw": True,
                "qualified": True,
                "frame_count": len(clean),
                "joint_dim": len(clean[0]["joint_positions"]) if clean else 0,
                "reason": "合格",
                "trajectory": clean,
            }
        last_fail = reason
    return {
        "found_raw": seen_raw,
        "qualified": False,
        "frame_count": 0,
        "joint_dim": 0,
        "reason": last_fail or "未找到轨迹字段",
        "trajectory": [],
    }


def build_pseudo_real_trajectory(sim_traj: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    无真机轨迹时的对照轨迹：在仿真轨迹上对关节角施加可重复偏置。

    仅用于打通回流链路；有真机数据后应被 extract_real_trajectory 替换。
    """
    sim = normalize_trajectory(sim_traj)
    out: list[dict[str, Any]] = []
    for frame in sim:
        joints = [float(x) * 1.15 + 0.05 for x in (frame.get("joint_positions") or [])]
        out.append({"t": frame.get("t", 0), "joint_positions": joints})
    return out


def resolve_rsr_policy(*, require_real_trajectory: bool = False) -> dict[str, Any]:
    """
    第12期策略：
    - prefer_real（默认）：有合格真轨迹用真；否则允许伪对照
    - require_real：无合格真轨迹则跳过（实验室严模式，默认关）
    """
    require_real = bool(require_real_trajectory)
    return {
        "policy": "require_real" if require_real else "prefer_real",
        "require_real_trajectory": require_real,
        "allow_pseudo_real": not require_real,
    }


def run_rsr_iteration(
    engine: Any,
    sim_traj: list[dict[str, Any]] | None,
    robot_result: dict[str, Any] | None = None,
    *,
    gain: float = 0.5,
    allow_pseudo_real: bool | None = None,
    require_real_trajectory: bool | None = None,
) -> dict[str, Any]:
    """
    执行一次：取对照轨迹 → 算偏差 → 写回物理参数。

    硬门槛：一旦有合格真轨迹，必须用真轨迹，禁止静默改伪对照。
    """
    # 策略：require_real=True 最优先关伪对照；否则尊重 allow_pseudo；默认允许伪对照
    if require_real_trajectory is True:
        allow_pseudo = False
    elif allow_pseudo_real is not None:
        allow_pseudo = bool(allow_pseudo_real)
    else:
        allow_pseudo = True
    policy_info = resolve_rsr_policy(require_real_trajectory=not allow_pseudo)

    sim = normalize_trajectory(sim_traj)
    report = extract_real_trajectory_report(robot_result)
    real = list(report.get("trajectory") or [])
    base_meta: dict[str, Any] = {
        "policy": policy_info["policy"],
        "require_real_trajectory": bool(policy_info["require_real_trajectory"]),
        "reference_frame_count": 0,
        "extract_reason": str(report.get("reason") or ""),
    }

    if real:
        # 硬门槛：有合格真轨迹 → 必须 robot
        source = "robot"
        base_meta["reference_frame_count"] = len(real)
    else:
        if not allow_pseudo or not sim:
            msg = "无合格真机轨迹且当前策略不允许伪对照，已跳过 RSR"
            if not sim:
                msg = "无仿真轨迹，无法做 RSR"
            return {
                "ok": False,
                "skipped": True,
                "reference_source": "",
                "message": msg,
                "deviation": None,
                "calibration": None,
                **base_meta,
            }
        real = build_pseudo_real_trajectory(sim)
        source = "pseudo_real"
        base_meta["reference_frame_count"] = len(real)

    deviation = compute_trajectory_deviation(sim, real)
    calibration = apply_calibration_to_engine(engine, deviation, gain=gain)
    return {
        "ok": bool(calibration.get("ok")),
        "skipped": False,
        "reference_source": source,
        "deviation": deviation,
        "calibration": calibration,
        "message": calibration.get("message") or deviation.get("message") or "RSR 完成",
        **base_meta,
    }
