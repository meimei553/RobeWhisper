# -*- coding: utf-8 -*-
"""
平面二连杆朝 xy 示意（补强包一 · 步骤 2）

教学几何，不是工业逆解；达不到则返回 None，由引擎回退旧示意。
连杆长度与 builtin_arm2 / builtin_arm2_contact 一致。
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from core.pose_grounding_contract import (
    METRIC_EE_GOAL_XY,
    METRIC_OBJECT_XPOS,
    METRIC_POSE_SOURCE,
    POSE_SOURCE_NONE,
    POSE_SOURCE_SCENE,
    POSE_SOURCE_UNCERTAIN,
    empty_pose_metrics,
    sanitize_pose_metrics,
)
from core.schemas import TaskSpec

# 与 MJCF fromto 长度一致
LINK1_LEN = 0.25
LINK2_LEN = 0.20
J1_RANGE = (-2.8, 2.8)
J2_RANGE = (-2.5, 2.5)


def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def joints_toward_xy(
    x: float,
    y: float,
    *,
    l1: float = LINK1_LEN,
    l2: float = LINK2_LEN,
) -> list[float] | None:
    """平面二连杆：末端朝 (x,y)。肘部取负角，贴近旧 grab 示意。失败返回 None。"""
    r2 = float(x) * float(x) + float(y) * float(y)
    r = math.sqrt(r2)
    if r < 1e-5:
        return None
    max_r = l1 + l2 - 1e-4
    min_r = abs(l1 - l2) + 1e-4
    xx, yy = float(x), float(y)
    if r > max_r:
        s = max_r / r
        xx, yy = xx * s, yy * s
        r2 = xx * xx + yy * yy
        r = max_r
    elif r < min_r:
        return None
    c2 = (r2 - l1 * l1 - l2 * l2) / (2.0 * l1 * l2)
    c2 = _clip(c2, -1.0, 1.0)
    s2 = -math.sqrt(max(0.0, 1.0 - c2 * c2))
    q2 = math.atan2(s2, c2)
    q1 = math.atan2(yy, xx) - math.atan2(l2 * s2, l1 + l2 * c2)
    q1 = _clip(q1, J1_RANGE[0], J1_RANGE[1])
    q2 = _clip(q2, J2_RANGE[0], J2_RANGE[1])
    return [round(q1, 6), round(q2, 6)]


def build_pose_metrics_for_aim(
    *,
    has_scene: bool,
    action: str,
    object_xpos: list[float] | None,
    aimed: bool,
    goal_xy: list[float] | None,
) -> dict[str, Any]:
    """组装位姿旁路；无场景走 sanitize 清坐标。"""
    act = str(action or "").strip().lower()
    if not has_scene:
        return sanitize_pose_metrics(empty_pose_metrics(has_scene=False), has_scene=False)
    xpos = [float(v) for v in object_xpos] if object_xpos and len(object_xpos) >= 2 else None
    if act not in {"grab", "place"}:
        return sanitize_pose_metrics(
            {
                METRIC_POSE_SOURCE: POSE_SOURCE_NONE,
                METRIC_OBJECT_XPOS: xpos,
                METRIC_EE_GOAL_XY: None,
            },
            has_scene=True,
        )
    if aimed and xpos is not None:
        return sanitize_pose_metrics(
            {
                METRIC_POSE_SOURCE: POSE_SOURCE_SCENE,
                METRIC_OBJECT_XPOS: xpos,
                METRIC_EE_GOAL_XY: goal_xy or [xpos[0], xpos[1]],
            },
            has_scene=True,
        )
    return sanitize_pose_metrics(
        {
            METRIC_POSE_SOURCE: POSE_SOURCE_UNCERTAIN,
            METRIC_OBJECT_XPOS: xpos,
            METRIC_EE_GOAL_XY: goal_xy,
        },
        has_scene=True,
    )


def apply_scene_aim_to_task(
    task: TaskSpec,
    *,
    has_scene: bool,
    object_xpos: list[float] | None,
) -> tuple[TaskSpec, dict[str, Any]]:
    """
    grab/place 且有物体坐标时写入 joint_targets（若调用方尚未指定）。
    返回（可能改过的 task, pose metrics）。
    """
    act = str(task.action or "").strip().lower()
    params = dict(task.params or {})
    already = "joint_targets" in params or "ctrl" in params
    aimed = False
    goal: list[float] | None = None
    new_task = task
    if has_scene and act in {"grab", "place"} and object_xpos and len(object_xpos) >= 2 and not already:
        joints = joints_toward_xy(float(object_xpos[0]), float(object_xpos[1]))
        if joints is not None:
            params["joint_targets"] = joints
            new_task = replace(task, params=params)
            aimed = True
            goal = [round(float(object_xpos[0]), 6), round(float(object_xpos[1]), 6)]
    pose_m = build_pose_metrics_for_aim(
        has_scene=has_scene,
        action=act,
        object_xpos=object_xpos,
        aimed=aimed,
        goal_xy=goal,
    )
    return new_task, pose_m
