# -*- coding: utf-8 -*-
"""
多步编排契约（第 14 期 · 步骤 1）

TaskSpec.steps：有序子任务列表（可选）。
与 params[\"steps\"]（单次动作内部仿真细分步数）不是同一概念。
"""

from __future__ import annotations

from typing import Any

from core.action_catalog import ALLOWED_ACTIONS, is_allowed_action

# 多步编排上限（过长则拒绝，步骤2解析时落实）
MAX_MULTI_STEPS = 5

# 单次仿真细分：写在 params 里的键名（历史兼容，勿与 TaskSpec.steps 混淆）
SIM_SUBSTEPS_PARAM_KEY = "steps"

# 子步字典允许的键
STEP_KEYS = frozenset({"action", "target", "constraints", "params"})


def empty_steps() -> list[dict[str, Any]]:
    """缺省：无多步编排（等价旧单步 TaskSpec）。"""
    return []


def is_multi_step(steps: list[dict[str, Any]] | None) -> bool:
    """是否启用多步编排。"""
    return bool(steps) and len(steps) >= 1


def normalize_step_item(raw: Any) -> dict[str, Any] | None:
    """
    将一项子任务规范为 {action, target, constraints, params}。
    不合法返回 None。
    """
    if not isinstance(raw, dict):
        return None
    action = str(raw.get("action", "") or "").strip().lower()
    if not action or action not in ALLOWED_ACTIONS:
        return None
    target = str(raw.get("target", "") or "").strip()
    constraints = raw.get("constraints")
    if not isinstance(constraints, dict):
        constraints = {}
    params = raw.get("params")
    if not isinstance(params, dict):
        params = {}
    return {
        "action": action,
        "target": target,
        "constraints": dict(constraints),
        "params": dict(params),
    }


def normalize_steps(raw: Any, *, max_steps: int = MAX_MULTI_STEPS) -> list[dict[str, Any]]:
    """
    规范化 steps 列表；非法项跳过。
    超过 max_steps 时截断（步骤2可改为整单拒绝；步骤1契约允许截断语义）。
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        step = normalize_step_item(item)
        if step is None:
            continue
        out.append(step)
        if len(out) >= max_steps:
            break
    return out


def validate_steps_list(steps: list[dict[str, Any]] | None) -> bool:
    """列表是否全部合法且不超过上限。"""
    if steps is None:
        return True
    if not isinstance(steps, list):
        return False
    if len(steps) > MAX_MULTI_STEPS:
        return False
    for item in steps:
        if normalize_step_item(item) is None:
            return False
    return True


def primary_action_from_spec(
    *,
    action: str,
    steps: list[dict[str, Any]] | None,
) -> str:
    """
    对外摘要用的主 action：
    - 无多步：用顶层 action
    - 有多步：优先顶层 action；若空则取首步 action
    """
    top = str(action or "").strip().lower()
    if top:
        return top
    if steps:
        return str(steps[0].get("action") or "")
    return ""


def sim_substeps_note() -> str:
    """给人看的区分说明（网站/文档可引用）。"""
    return (
        "注意：params 里的 steps 表示「单次动作内部仿真细分步数」；"
        "TaskSpec.steps 表示「先做 A 再做 B」的多步编排。二者不要混用。"
    )


def format_multi_step_message(
    task_spec: dict[str, Any] | None = None,
    sim_metrics: dict[str, Any] | None = None,
    multi_meta: dict[str, Any] | None = None,
) -> str:
    """聊天/诊断用的多步人话；非多步返回空串。"""
    spec = task_spec or {}
    metrics = sim_metrics or {}
    meta = multi_meta or {}
    steps = spec.get("steps") if isinstance(spec.get("steps"), list) else []
    count = int(metrics.get("step_count") or meta.get("step_count") or (len(steps) if steps else 0))
    if count < 2 and not is_multi_step(steps):
        return ""
    actions = metrics.get("step_actions") or meta.get("step_actions")
    if not isinstance(actions, list) or not actions:
        actions = [str(s.get("action") or "") for s in steps if isinstance(s, dict)]
    actions = [a for a in actions if a]
    chain = " → ".join(actions) if actions else ""
    failed = meta.get("failed_at")
    if failed:
        return f"多步试机：第 {failed}/{count} 步未完成" + (f"（计划：{chain}）" if chain else "")
    return f"多步试机：共 {count} 步" + (f"（{chain}）" if chain else "") + "；教学编排，非工业连续作业"


def multi_step_diagnosis_lines(
    task_spec: dict[str, Any] | None = None,
    sim_metrics: dict[str, Any] | None = None,
    multi_meta: dict[str, Any] | None = None,
) -> list[str]:
    """诊断面板多步行。"""
    msg = format_multi_step_message(task_spec, sim_metrics, multi_meta)
    if not msg:
        return []
    lines = [msg, sim_substeps_note()]
    return lines


def assert_action_allowed(action: str | None) -> bool:
    """薄封装，便于烟雾引用。"""
    return is_allowed_action(action)
