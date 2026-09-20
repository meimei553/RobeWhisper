# -*- coding: utf-8 -*-
"""
虚实轨迹偏差度量（阶段 6 · 步骤 1）。

轨迹帧约定（通用，不绑引擎/ROS）：
  {"t": int|float, "joint_positions": [float, ...]}

输出偏差指标为标量字典，供后续参数校准使用。
"""

from __future__ import annotations

from typing import Any


def normalize_trajectory(frames: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """清洗轨迹：只保留 t 与 joint_positions。"""
    out: list[dict[str, Any]] = []
    for i, frame in enumerate(frames or []):
        if not isinstance(frame, dict):
            continue
        joints = frame.get("joint_positions")
        if not isinstance(joints, list):
            continue
        clean_joints = []
        for x in joints:
            try:
                clean_joints.append(float(x))
            except (TypeError, ValueError):
                clean_joints.append(0.0)
        t_raw = frame.get("t", i)
        try:
            t_val: float | int = float(t_raw)
        except (TypeError, ValueError):
            t_val = float(i)
        out.append({"t": t_val, "joint_positions": clean_joints})
    return out


def _pad_joints(a: list[float], b: list[float]) -> tuple[list[float], list[float]]:
    n = max(len(a), len(b))
    aa = list(a) + [0.0] * (n - len(a))
    bb = list(b) + [0.0] * (n - len(b))
    return aa, bb


def pairwise_joint_mae(sim_frame: dict[str, Any], real_frame: dict[str, Any]) -> float:
    """单帧关节角平均绝对误差。"""
    a = list(sim_frame.get("joint_positions") or [])
    b = list(real_frame.get("joint_positions") or [])
    if not a and not b:
        return 0.0
    aa, bb = _pad_joints([float(x) for x in a], [float(x) for x in b])
    if not aa:
        return 0.0
    return sum(abs(x - y) for x, y in zip(aa, bb)) / len(aa)


def compute_trajectory_deviation(
    sim_traj: list[dict[str, Any]] | None,
    real_traj: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """
    计算两条轨迹的偏差指标。

    返回：
      ok: 是否成功算出
      mae: 全轨迹平均绝对误差（关节）
      rmse: 均方根误差
      final_mae: 末帧 MAE
      max_mae: 帧间最大 MAE
      aligned_frames: 对齐后参与比较的帧数
      message: 说明
    """
    sim = normalize_trajectory(sim_traj)
    real = normalize_trajectory(real_traj)
    if not sim or not real:
        return {
            "ok": False,
            "mae": None,
            "rmse": None,
            "final_mae": None,
            "max_mae": None,
            "aligned_frames": 0,
            "message": "轨迹为空，无法比较",
        }

    n = min(len(sim), len(real))
    maes: list[float] = []
    sq: list[float] = []
    for i in range(n):
        m = pairwise_joint_mae(sim[i], real[i])
        maes.append(m)
        # 用该帧各关节误差平方均值再开方，累加后再整体开方
        a = [float(x) for x in (sim[i].get("joint_positions") or [])]
        b = [float(x) for x in (real[i].get("joint_positions") or [])]
        aa, bb = _pad_joints(a, b)
        if aa:
            sq.append(sum((x - y) ** 2 for x, y in zip(aa, bb)) / len(aa))

    mae = sum(maes) / len(maes) if maes else 0.0
    rmse = (sum(sq) / len(sq)) ** 0.5 if sq else 0.0
    return {
        "ok": True,
        "mae": mae,
        "rmse": rmse,
        "final_mae": maes[-1] if maes else 0.0,
        "max_mae": max(maes) if maes else 0.0,
        "aligned_frames": n,
        "sim_frames": len(sim),
        "real_frames": len(real),
        "message": "偏差计算完成",
    }
