# -*- coding: utf-8 -*-
"""
场景位姿示意契约（补强包一 · 步骤 1）

位姿只进 SimResult.metrics / 实验旁路，不改 TaskSpec 主字段名。
无接触场景时禁止填写物体坐标（防止假接地）。
"""

from __future__ import annotations

from typing import Any

# pose_source：坐标从哪来（教学级，不是相机）
POSE_SOURCE_SCENE = "scene_model"
POSE_SOURCE_NONE = "none"
POSE_SOURCE_UNCERTAIN = "uncertain"
POSE_SOURCE_VALUES = frozenset(
    {
        POSE_SOURCE_SCENE,
        POSE_SOURCE_NONE,
        POSE_SOURCE_UNCERTAIN,
    }
)

METRIC_POSE_SOURCE = "pose_source"
METRIC_OBJECT_XPOS = "object_xpos"
METRIC_EE_GOAL_XY = "ee_goal_xy"

POSE_METRIC_KEYS = (
    METRIC_POSE_SOURCE,
    METRIC_OBJECT_XPOS,
    METRIC_EE_GOAL_XY,
)

# 实验旁路「本次用了哪些代理」键名（A6，步骤3落盘时写入 extra）
PROXY_SUMMARY_KEYS = (
    "pose_source",
    "grasp_proxy",
    "contact_scene",
    "multi_step",
    "step_count",
    "rsr_reference_source",
)


def validate_pose_source(value: str | None) -> bool:
    return str(value or "") in POSE_SOURCE_VALUES


def empty_pose_metrics(*, has_scene: bool) -> dict[str, Any]:
    """
    位姿旁路占位。
    无场景：pose_source=none，坐标必须为 None（禁止假坐标）。
    有场景：步骤1只占位 uncertain，真实 xpos 留给步骤2引擎填写。
    """
    if has_scene:
        return {
            METRIC_POSE_SOURCE: POSE_SOURCE_UNCERTAIN,
            METRIC_OBJECT_XPOS: None,
            METRIC_EE_GOAL_XY: None,
        }
    return {
        METRIC_POSE_SOURCE: POSE_SOURCE_NONE,
        METRIC_OBJECT_XPOS: None,
        METRIC_EE_GOAL_XY: None,
    }


def sanitize_pose_metrics(metrics: dict[str, Any] | None, *, has_scene: bool) -> dict[str, Any]:
    """无场景时清掉伪造坐标；有场景才允许保留 xpos/goal。"""
    m = dict(metrics or {})
    if not has_scene:
        m[METRIC_POSE_SOURCE] = POSE_SOURCE_NONE
        m[METRIC_OBJECT_XPOS] = None
        m[METRIC_EE_GOAL_XY] = None
        return m
    src = str(m.get(METRIC_POSE_SOURCE) or POSE_SOURCE_UNCERTAIN)
    if src not in POSE_SOURCE_VALUES:
        src = POSE_SOURCE_UNCERTAIN
    m[METRIC_POSE_SOURCE] = src
    return m


def has_forged_object_pose(metrics: dict[str, Any] | None, *, has_scene: bool) -> bool:
    """无场景却带了物体坐标 → 契约违规。"""
    if has_scene:
        return False
    m = metrics if isinstance(metrics, dict) else {}
    if m.get(METRIC_OBJECT_XPOS) not in (None, "", [], ()):
        return True
    if m.get(METRIC_EE_GOAL_XY) not in (None, "", [], ()):
        return True
    if str(m.get(METRIC_POSE_SOURCE) or "") == POSE_SOURCE_SCENE:
        return True
    return False


def pose_source_label(value: str | None) -> str:
    """零基础人话（强调非相机）。"""
    v = str(value or "").strip().lower()
    if v == POSE_SOURCE_SCENE:
        return "朝仿真里的物体位置示意（不是相机看到的）"
    if v == POSE_SOURCE_NONE:
        return "当前无试机物体，只是关节示意（无场景坐标）"
    if v == POSE_SOURCE_UNCERTAIN:
        return "有接触场景但尚未用物体坐标生成目标（或回退了旧示意；仍不是相机）"
    if not v:
        return "（无位姿来源）"
    return f"其它（{v}）"


def build_proxy_summary(
    *,
    metrics: dict[str, Any] | None = None,
    multi_step: dict[str, Any] | None = None,
    rsr: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """实验/诊断用的代理一览（只摘旁路，无密钥）。"""
    m = metrics if isinstance(metrics, dict) else {}
    ms = multi_step if isinstance(multi_step, dict) else {}
    r = rsr if isinstance(rsr, dict) else {}
    step_count = m.get("step_count")
    if step_count is None:
        step_count = ms.get("step_count")
    is_multi = bool(m.get("multi_step") or ms or (isinstance(step_count, int) and step_count >= 2))
    return {
        "pose_source": m.get(METRIC_POSE_SOURCE) or POSE_SOURCE_NONE,
        "grasp_proxy": m.get("grasp_proxy") or "-",
        "contact_scene": m.get("contact_scene"),
        "multi_step": is_multi,
        "step_count": step_count if step_count is not None else "-",
        "rsr_reference_source": r.get("reference_source") or "-",
    }


def format_proxy_summary_lines(summary: dict[str, Any] | None) -> list[str]:
    """能力区一眼可读：位姿 / 接触 / 多步 / RSR（A6）。"""
    s = summary if isinstance(summary, dict) else {}
    from core.contact_scene_contract import contact_reason_zh, grasp_proxy_label

    pose = pose_source_label(s.get("pose_source"))
    grasp = grasp_proxy_label(s.get("grasp_proxy"))
    reason = contact_reason_zh(s.get("grasp_proxy"))
    grasp_bit = f"{grasp}｜原因：{reason}" if reason else grasp
    multi = "是" if s.get("multi_step") else "否"
    sc = s.get("step_count")
    if multi == "是" and sc not in (None, "", "-"):
        multi = f"是（{sc} 步）"
    rsr_raw = str(s.get("rsr_reference_source") or "-").strip().lower()
    if rsr_raw in {"", "-", "none"}:
        rsr_zh = "未做"
    elif rsr_raw in {"pseudo_real", "pseudo", "synthetic"}:
        rsr_zh = "伪对照（不是真回流）"
    elif rsr_raw in {"robot", "real", "real_robot"}:
        rsr_zh = "真轨迹"
    else:
        rsr_zh = rsr_raw
    return [
        f"位姿来源：{pose}",
        f"接触代理：{grasp_bit}",
        f"多步试机：{multi}",
        f"RSR对照：{rsr_zh}",
    ]


def format_pose_grounding_message(metrics: dict[str, Any] | None) -> str:
    """聊天用一句位姿示意；无字段则空串。"""
    m = metrics if isinstance(metrics, dict) else {}
    if METRIC_POSE_SOURCE not in m:
        return ""
    src = str(m.get(METRIC_POSE_SOURCE) or "")
    label = pose_source_label(src)
    bits = [label]
    goal = m.get(METRIC_EE_GOAL_XY)
    if isinstance(goal, (list, tuple)) and len(goal) >= 2:
        try:
            bits.append(f"目标平面≈({float(goal[0]):.2f},{float(goal[1]):.2f})")
        except (TypeError, ValueError):
            pass
    return "；".join(bits)


def pose_grounding_diagnosis_lines(metrics: dict[str, Any] | None) -> list[str]:
    """诊断：场景位姿示意 + 非相机边界。"""
    m = metrics if isinstance(metrics, dict) else {}
    if METRIC_POSE_SOURCE not in m:
        return []
    msg = format_pose_grounding_message(m)
    lines = [f"场景位姿示意：{msg}"]
    src = str(m.get(METRIC_POSE_SOURCE) or "")
    if src == POSE_SOURCE_NONE:
        lines.append("说明：当前没有用场景物体坐标。默认臂只是关节示意；要朝方块伸请切换接触试机场景。")
    elif src == POSE_SOURCE_SCENE:
        lines.append("说明：坐标来自仿真模型里的方块，不是相机看见的红色杯子；也不代表已经抓住。")
    elif src == POSE_SOURCE_UNCERTAIN:
        lines.append("说明：有接触场景，但本次未按物体坐标生成目标（可能复用了旧轨迹或回退了旧示意；仍不是相机）。")
    return lines
