# -*- coding: utf-8 -*-
"""从模型文本提取并校验 TaskSpec（阶段 3 · 步骤 2 强化版）。"""

from __future__ import annotations

import json
import re
from typing import Any

from core.schemas import ApiResult, TaskSpec
from core.action_catalog import ALLOWED_ACTIONS
from plugins.llm.base import (
    FRIENDLY_BLOCKED,
    LLM_CODE_PARSE_FAILED,
    LLM_CODE_REJECTED,
)

# 动作白名单改由 core.action_catalog 统一维护（第14期）

# 常见别名归一
ACTION_ALIASES = {
    "pick": "grab",
    "pick_up": "grab",
    "grasp": "grab",
    "take": "grab",
    "put": "place",
    "drop": "place",
    "go": "move",
    "reset": "home",
    "zero": "home",
}

# params 允许的简单键（其余忽略，避免模型乱塞危险字段）
ALLOWED_PARAM_KEYS = frozenset(
    {
        "steps",
        "nsub",
        "joint_delta",
        "joint_targets",
        "ctrl",
        "model_ref",
        "seconds",  # wait 动作可选
        "side",
    }
)

_MAX_USER_CHARS = 500
_MAX_TARGET_CHARS = 64


def normalize_action(action: str) -> str:
    a = (action or "").strip().lower().replace("-", "_").replace(" ", "_")
    return ACTION_ALIASES.get(a, a)


def extract_json_object(text: str) -> dict[str, Any] | None:
    """尝试从模型输出中提取第一个 JSON 对象。"""
    raw = (text or "").strip()
    if not raw:
        return None
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        raw = fence.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start : end + 1]
        else:
            return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _sanitize_params(params: Any) -> dict[str, Any]:
    if not isinstance(params, dict):
        return {}
    clean: dict[str, Any] = {}
    for key, value in params.items():
        k = str(key)
        if k not in ALLOWED_PARAM_KEYS:
            continue
        # 拒绝明显非数据内容
        if isinstance(value, str) and any(x in value.lower() for x in ("rm -rf", "http://", "https://", "api_key")):
            continue
        clean[k] = value
    return clean


def _sanitize_constraints(constraints: Any) -> dict[str, Any]:
    if not isinstance(constraints, dict):
        return {}
    # 只保留简单 JSON 可序列化值
    clean: dict[str, Any] = {}
    for key, value in constraints.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            clean[str(key)] = value
        elif isinstance(value, list) and all(isinstance(x, (int, float)) for x in value):
            clean[str(key)] = value
    return clean


def task_spec_from_model_dict(data: dict[str, Any], task_id: str, raw_text: str, source: str) -> ApiResult:
    """将模型 JSON 转为 TaskSpec；不合法则失败。"""
    from core.multi_step_contract import (
        MAX_MULTI_STEPS,
        normalize_steps,
        primary_action_from_spec,
    )

    if not isinstance(data, dict):
        return ApiResult.fail(LLM_CODE_PARSE_FAILED, FRIENDLY_BLOCKED)

    raw_steps = data.get("steps")
    # 明确过长 → 拒绝（比静默截断更易懂）
    if isinstance(raw_steps, list) and len(raw_steps) > MAX_MULTI_STEPS:
        return ApiResult.fail(
            LLM_CODE_REJECTED,
            f"子动作过多（最多 {MAX_MULTI_STEPS} 步），请拆开再说。",
        )

    steps = normalize_steps(raw_steps) if raw_steps is not None else []
    # 若提供了 steps 但一项都合法不了
    if isinstance(raw_steps, list) and len(raw_steps) > 0 and not steps:
        return ApiResult.fail(LLM_CODE_REJECTED, "多步指令里没有可识别的合法动作，请换一种说法。")

    action = normalize_action(str(data.get("action", "")))
    if not action and steps:
        action = primary_action_from_spec(action="", steps=steps)
    if not action:
        return ApiResult.fail(LLM_CODE_REJECTED, "暂时无法识别该指令，请换一种说法试试。")
    if action not in ALLOWED_ACTIONS:
        return ApiResult.fail(LLM_CODE_REJECTED, "该动作不受支持，请换一种说法试试。")

    target = str(data.get("target", "") or "").strip()
    if len(target) > _MAX_TARGET_CHARS:
        target = target[:_MAX_TARGET_CHARS]
    # 有多步且顶层 target 空时，用首步 target 作摘要
    if not target and steps:
        target = str(steps[0].get("target") or "")

    constraints = _sanitize_constraints(data.get("constraints"))
    params = _sanitize_params(data.get("params"))
    if "steps" not in params and action != "wait":
        params["steps"] = 3

    # 子步 params 也过一遍白名单
    clean_steps: list[dict[str, Any]] = []
    for st in steps:
        st_params = _sanitize_params(st.get("params"))
        if "steps" not in st_params and st.get("action") not in {"wait", "home"}:
            st_params["steps"] = 3
        clean_steps.append(
            {
                "action": st["action"],
                "target": str(st.get("target") or "")[:_MAX_TARGET_CHARS],
                "constraints": _sanitize_constraints(st.get("constraints")),
                "params": st_params,
            }
        )

    spec = TaskSpec(
        task_id=task_id,
        action=action,
        target=target,
        constraints=constraints,
        params=params,
        source=source,
        raw_text=raw_text,
        steps=clean_steps,
    )
    return ApiResult.success("解析成功", data={"task_spec": spec.to_dict()})


def parse_model_text_to_task(text: str, task_id: str, raw_user: str, source: str) -> ApiResult:
    user = (raw_user or "").strip()
    if not user:
        return ApiResult.fail(LLM_CODE_PARSE_FAILED, FRIENDLY_BLOCKED)
    if len(user) > _MAX_USER_CHARS:
        return ApiResult.fail(LLM_CODE_REJECTED, "指令过长，请缩短后再试。")

    data = extract_json_object(text)
    if data is None:
        return ApiResult.fail(LLM_CODE_PARSE_FAILED, FRIENDLY_BLOCKED)
    return task_spec_from_model_dict(data, task_id=task_id, raw_text=user, source=source)
