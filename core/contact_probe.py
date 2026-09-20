# -*- coding: utf-8 -*-
"""
接触/接近度量（第 13 期 · 步骤 2）

教学级 grasp proxy：根据接触、距离、物体位移给出旁路指标。
不宣称工业抓住；无夹爪时「ok」仅表示试机代理通过。
"""

from __future__ import annotations

import math
from typing import Any

from core.contact_scene_contract import (
    CONTACT_EE_GEOM,
    CONTACT_OBJECT_BODY,
    CONTACT_OBJECT_GEOM,
    GRASP_PROXY_NO_CONTACT,
    GRASP_PROXY_NO_SCENE,
    GRASP_PROXY_OK,
    GRASP_PROXY_UNCERTAIN,
    METRIC_CONTACT_DETECTED,
    METRIC_CONTACT_SCENE,
    METRIC_EE_OBJECT_DISTANCE,
    METRIC_GRASP_PROXY,
    METRIC_OBJECT_MOVED,
    empty_contact_metrics,
)

# 接近阈值（米）：末端探头与物体中心
_NEAR_DIST = 0.10
_UNCERTAIN_DIST = 0.18
# 物体位移阈值（米）
_MOVED_EPS = 0.008


def decide_grasp_proxy(
    *,
    has_scene: bool,
    action: str,
    contact_detected: bool,
    object_moved: bool,
    ee_object_distance: float | None,
) -> str:
    """纯函数：由观测决定 grasp_proxy。"""
    if not has_scene:
        return GRASP_PROXY_NO_SCENE

    act = (action or "").strip().lower()
    dist = ee_object_distance
    near = dist is not None and dist <= _NEAR_DIST
    mid = dist is not None and dist <= _UNCERTAIN_DIST

    if act in {"grab", "place"}:
        # 弱代理：有接触，或（靠近且物体被推动）
        if contact_detected or (near and object_moved):
            return GRASP_PROXY_OK
        if near or mid or object_moved:
            return GRASP_PROXY_UNCERTAIN
        return GRASP_PROXY_NO_CONTACT

    # 非抓放：只报告场景状态，不给 ok
    if contact_detected:
        return GRASP_PROXY_UNCERTAIN
    if near:
        return GRASP_PROXY_UNCERTAIN
    return GRASP_PROXY_NO_CONTACT


def build_contact_metrics(
    *,
    has_scene: bool,
    action: str,
    contact_detected: bool = False,
    object_moved: bool = False,
    ee_object_distance: float | None = None,
) -> dict[str, Any]:
    """组装写入 SimResult.metrics 的接触旁路字典。"""
    if not has_scene:
        return empty_contact_metrics(has_scene=False)

    proxy = decide_grasp_proxy(
        has_scene=True,
        action=action,
        contact_detected=bool(contact_detected),
        object_moved=bool(object_moved),
        ee_object_distance=ee_object_distance,
    )
    dist_out: float | None
    if ee_object_distance is None:
        dist_out = None
    else:
        dist_out = round(float(ee_object_distance), 6)

    return {
        METRIC_CONTACT_SCENE: True,
        METRIC_CONTACT_DETECTED: bool(contact_detected),
        METRIC_GRASP_PROXY: proxy,
        METRIC_OBJECT_MOVED: bool(object_moved),
        METRIC_EE_OBJECT_DISTANCE: dist_out,
    }


def _geom_id(model: Any, name: str) -> int:
    import mujoco

    gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)
    return int(gid)


def _body_id(model: Any, name: str) -> int:
    import mujoco

    bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
    return int(bid)


def mujoco_scene_has_object(model: Any) -> bool:
    """模型里是否有约定自由物体 body。"""
    try:
        return _body_id(model, CONTACT_OBJECT_BODY) >= 0
    except Exception:
        return False


def mujoco_object_xpos(model: Any, data: Any) -> list[float] | None:
    try:
        bid = _body_id(model, CONTACT_OBJECT_BODY)
        if bid < 0:
            return None
        return [float(data.xpos[bid][0]), float(data.xpos[bid][1]), float(data.xpos[bid][2])]
    except Exception:
        return None


def mujoco_ee_object_distance(model: Any, data: Any) -> float | None:
    try:
        ee = _geom_id(model, CONTACT_EE_GEOM)
        obj = _geom_id(model, CONTACT_OBJECT_GEOM)
        if ee < 0 or obj < 0:
            return None
        a = data.geom_xpos[ee]
        b = data.geom_xpos[obj]
        dx = float(a[0] - b[0])
        dy = float(a[1] - b[1])
        dz = float(a[2] - b[2])
        return math.sqrt(dx * dx + dy * dy + dz * dz)
    except Exception:
        return None


def mujoco_ee_object_contact(model: Any, data: Any) -> bool:
    """是否存在末端(或小臂)与物体的接触对。"""
    import mujoco

    try:
        ee = _geom_id(model, CONTACT_EE_GEOM)
        obj = _geom_id(model, CONTACT_OBJECT_GEOM)
        link2 = _geom_id(model, "link2_geom")
    except Exception:
        return False
    if obj < 0:
        return False

    allow_arm = {g for g in (ee, link2) if g >= 0}
    if not allow_arm:
        return False

    for i in range(int(data.ncon)):
        c = data.contact[i]
        g1 = int(c.geom1)
        g2 = int(c.geom2)
        pair = {g1, g2}
        if obj in pair and (pair & allow_arm):
            return True
    return False


def evaluate_mujoco_contact(
    model: Any,
    data: Any,
    *,
    action: str,
    object_xpos_before: list[float] | None,
) -> dict[str, Any]:
    """从当前 MjModel/MjData 汇总接触旁路 metrics。"""
    has_scene = mujoco_scene_has_object(model)
    if not has_scene:
        return build_contact_metrics(has_scene=False, action=action)

    # 推进一次碰撞检测，确保 ncon 最新
    try:
        import mujoco

        mujoco.mj_forward(model, data)
    except Exception:
        pass

    contact = mujoco_ee_object_contact(model, data)
    dist = mujoco_ee_object_distance(model, data)
    after = mujoco_object_xpos(model, data)
    moved = False
    if object_xpos_before and after and len(object_xpos_before) >= 3 and len(after) >= 3:
        dmove = math.sqrt(
            sum((float(after[i]) - float(object_xpos_before[i])) ** 2 for i in range(3))
        )
        moved = dmove >= _MOVED_EPS

    return build_contact_metrics(
        has_scene=True,
        action=action,
        contact_detected=contact,
        object_moved=moved,
        ee_object_distance=dist,
    )
