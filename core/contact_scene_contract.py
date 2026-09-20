# -*- coding: utf-8 -*-
"""
接触试机场景契约（第 13 期 · 步骤 1）

只约定「场景怎么认、旁路字段叫什么」；真正的接触度量在步骤 2。
不改 TaskSpec / SimResult / ApiResult 主字段名——接触结果只进 metrics。
"""

from __future__ import annotations

from typing import Any

# 相对 MODELS_DIR 的接触场景路径
CONTACT_SCENE_MODEL_REL = "builtin_arm2_contact/model.xml"

# 场景内约定名（MJCF body/geom）
CONTACT_OBJECT_BODY = "object_block"
CONTACT_OBJECT_GEOM = "object_geom"
CONTACT_EE_GEOM = "ee"

# grasp_proxy 取值（教学代理，不是工业抓住判定）
GRASP_PROXY_OK = "ok"
GRASP_PROXY_NO_CONTACT = "no_contact"
GRASP_PROXY_NO_SCENE = "no_scene"
GRASP_PROXY_UNCERTAIN = "uncertain"
GRASP_PROXY_VALUES = frozenset(
    {
        GRASP_PROXY_OK,
        GRASP_PROXY_NO_CONTACT,
        GRASP_PROXY_NO_SCENE,
        GRASP_PROXY_UNCERTAIN,
    }
)

# SimResult.metrics 旁路键（只增不改主契约）
METRIC_CONTACT_DETECTED = "contact_detected"
METRIC_GRASP_PROXY = "grasp_proxy"
METRIC_OBJECT_MOVED = "object_moved"
METRIC_EE_OBJECT_DISTANCE = "ee_object_distance"
METRIC_CONTACT_SCENE = "contact_scene"

CONTACT_METRIC_KEYS = (
    METRIC_CONTACT_DETECTED,
    METRIC_GRASP_PROXY,
    METRIC_OBJECT_MOVED,
    METRIC_EE_OBJECT_DISTANCE,
    METRIC_CONTACT_SCENE,
)


def is_contact_scene_model_ref(model_ref: str | None) -> bool:
    """根据 model_ref 判断是否选用接触试机场景。"""
    raw = str(model_ref or "").strip().replace("\\", "/").lower()
    if not raw:
        return False
    if raw in {"builtin_arm2_contact", "contact", "arm2_contact"}:
        return True
    if CONTACT_SCENE_MODEL_REL.lower() in raw:
        return True
    if "builtin_arm2_contact" in raw:
        return True
    return False


def empty_contact_metrics(*, has_scene: bool) -> dict[str, Any]:
    """
    接触旁路占位（步骤1可写；步骤2再填真实值）。
    无场景时 grasp_proxy=no_scene，避免报假成功。
    """
    if has_scene:
        return {
            METRIC_CONTACT_SCENE: True,
            METRIC_CONTACT_DETECTED: False,
            METRIC_GRASP_PROXY: GRASP_PROXY_UNCERTAIN,
            METRIC_OBJECT_MOVED: False,
            METRIC_EE_OBJECT_DISTANCE: None,
        }
    return {
        METRIC_CONTACT_SCENE: False,
        METRIC_CONTACT_DETECTED: False,
        METRIC_GRASP_PROXY: GRASP_PROXY_NO_SCENE,
        METRIC_OBJECT_MOVED: False,
        METRIC_EE_OBJECT_DISTANCE: None,
    }


def validate_grasp_proxy(value: str | None) -> bool:
    """取值是否在约定枚举内。"""
    return str(value or "") in GRASP_PROXY_VALUES


def contact_reason_zh(value: str | None) -> str:
    """三种接触结果的短因（A2）：场景没开 / 够不着 / 碰到。"""
    v = str(value or "").strip().lower()
    if v == GRASP_PROXY_NO_SCENE:
        return "场景没开（无试机物体）"
    if v == GRASP_PROXY_NO_CONTACT:
        return "够不着或没碰到"
    if v == GRASP_PROXY_OK:
        return "碰到或近距推动（不是抓住）"
    if v == GRASP_PROXY_UNCERTAIN:
        return "有接近但不明确"
    return ""


def grasp_proxy_label(value: str | None) -> str:
    """grasp_proxy → 零基础人话（强调非工业抓住）。"""
    v = str(value or "").strip().lower()
    if v == GRASP_PROXY_OK:
        return "接触试机代理通过（碰到或近距推动；不是工业夹稳）"
    if v == GRASP_PROXY_NO_CONTACT:
        return "未检测到有效接触/接近"
    if v == GRASP_PROXY_NO_SCENE:
        return "当前模型无试机物体（只是关节示意）"
    if v == GRASP_PROXY_UNCERTAIN:
        return "有接近迹象但不明确（代理不确定）"
    if not v:
        return "（无接触结果）"
    return f"其它（{v}）"


def format_contact_trial_message(metrics: dict[str, Any] | None) -> str:
    """聊天/摘要用的一句接触试机说明。"""
    m = metrics if isinstance(metrics, dict) else {}
    if not m and m != {}:
        return "未报告（无仿真指标）"
    # 无接触相关键：旧实验/超时等
    if METRIC_GRASP_PROXY not in m and METRIC_CONTACT_SCENE not in m:
        return "未报告（本次无接触旁路字段）"

    proxy = str(m.get(METRIC_GRASP_PROXY) or "")
    label = grasp_proxy_label(proxy)
    bits = [label]
    if m.get(METRIC_CONTACT_DETECTED) is True:
        bits.append("接触=是")
    elif m.get(METRIC_CONTACT_SCENE) is True:
        bits.append("接触=否")
    dist = m.get(METRIC_EE_OBJECT_DISTANCE)
    if dist is not None:
        try:
            bits.append(f"末端-物体距离≈{float(dist):.3f}m")
        except (TypeError, ValueError):
            pass
    if m.get(METRIC_OBJECT_MOVED) is True:
        bits.append("物体有位移")
    return "；".join(bits)


def contact_trial_diagnosis_lines(metrics: dict[str, Any] | None) -> list[str]:
    """诊断区多行：接触试机结果 + 边界说明。"""
    m = metrics if isinstance(metrics, dict) else {}
    lines: list[str] = []
    if METRIC_GRASP_PROXY not in m and METRIC_CONTACT_SCENE not in m:
        return lines

    msg = format_contact_trial_message(m)
    proxy = str(m.get(METRIC_GRASP_PROXY) or "")
    reason = contact_reason_zh(proxy)
    if reason:
        lines.append(f"接触试机：{msg}｜原因：{reason}")
    else:
        lines.append(f"接触试机：{msg}")
    if proxy == GRASP_PROXY_NO_SCENE:
        lines.append(
            "说明：当前模型没有试机物体。若要做接触试机，请在「① 模型」切换到「接触试机场景」。"
        )
    elif proxy == GRASP_PROXY_OK:
        lines.append(
            "说明：这是教学级弱代理（末端碰到或近距推动物体），不代表夹爪已夹稳，也不代表现实已抓住。"
        )
    elif proxy == GRASP_PROXY_NO_CONTACT:
        lines.append("说明：仿真里臂动了，但没够到/碰到物体；可换接触场景或调整动作后再试。")
    elif proxy == GRASP_PROXY_UNCERTAIN:
        lines.append("说明：有接近但接触证据不足；可再跑一次或换角度试机。")
    return lines
