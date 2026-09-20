# -*- coding: utf-8 -*-
"""
多步自然语言粗解析（第 14 期 · 步骤 2）

供 Mock 识别「先…再… / 然后 / 接着」；API 仍主要靠 Prompt + JSON steps。
"""

from __future__ import annotations

import re
from typing import Any

from core.multi_step_contract import MAX_MULTI_STEPS


def _infer_target(raw: str) -> str:
    """与 MockLLM 同风格的目标推断（避免循环导入，本地复制精简表）。"""
    color_map = (
        ("红色", "red"),
        ("红", "red"),
        ("蓝色", "blue"),
        ("蓝", "blue"),
        ("绿色", "green"),
        ("绿", "green"),
        ("黄色", "yellow"),
        ("黄", "yellow"),
        ("黑色", "black"),
        ("白色", "white"),
        ("白", "white"),
    )
    object_map = (
        ("积木", "block"),
        ("方块", "block"),
        ("木块", "block"),
        ("杯子", "cup"),
        ("茶杯", "cup"),
        ("水瓶", "bottle"),
        ("瓶子", "bottle"),
        ("盒子", "box"),
        ("物块", "block"),
        ("工件", "workpiece"),
        ("零件", "part"),
    )
    color = ""
    for cn, en in color_map:
        if cn in raw:
            color = en
            break
    obj = ""
    for cn, en in object_map:
        if cn in raw:
            obj = en
            break
    if color and obj:
        return f"{color}_{obj}"
    if obj:
        return obj
    return ""


def infer_action(clause: str) -> str | None:
    """单句动作推断；无法识别返回 None。"""
    raw = (clause or "").strip()
    if not raw:
        return None
    low = raw.lower()
    if any(k in raw for k in ("等待", "等一下", "停一下", "停顿")) or "wait" in low:
        return "wait"
    if any(k in raw for k in ("回零", "复位", "归位")) or "home" in low:
        return "home"
    if any(k in raw for k in ("拿", "抓", "拾", "夹")):
        return "grab"
    if any(k in raw for k in ("放", "放下", "放到")):
        return "place"
    if any(k in raw for k in ("移", "动", "走", "转")):
        return "move"
    return None


def _clause_to_step(clause: str) -> dict[str, Any] | None:
    action = infer_action(clause)
    if action is None:
        return None
    target = _infer_target(clause)
    if action in {"grab", "place"} and not target:
        return None
    params: dict[str, Any] = {}
    if action in {"grab", "place", "move"}:
        params = {"steps": 3, "joint_delta": 0.1}
    elif action == "wait":
        params = {"seconds": 0.5}
    return {
        "action": action,
        "target": target,
        "constraints": {},
        "params": params,
    }


def _split_multi_clauses(raw: str) -> list[str] | None:
    """
    拆成子句。能拆出 ≥2 段才算多步候选。
    支持：先A再B / 先A然后B；A然后B；A再B；A接着B；A之后B
    """
    text = (raw or "").strip()
    if not text:
        return None

    # 先…再/然后/接着/之后…
    m = re.match(
        r"^先(.+?)(?:再|然后|接着|之后)(.+)$",
        text,
    )
    if m:
        left, right = m.group(1).strip(" ，,、"), m.group(2).strip(" ，,、")
        if left and right:
            return [left, right]

    # 无「先」：用连接词拆（仅当两侧都能识别动作时才采用）
    for sep in ("然后", "接着", "之后", "再"):
        if sep not in text:
            continue
        parts = [p.strip(" ，,、") for p in text.split(sep) if p.strip(" ，,、")]
        if len(parts) >= 2:
            return parts[:MAX_MULTI_STEPS]

    return None


def try_parse_multi_steps(raw: str) -> list[dict[str, Any]] | None:
    """
    若指令像多步编排，返回 steps 列表；否则 None（交给单步逻辑）。
    超过上限的子句丢弃尾部。
    """
    clauses = _split_multi_clauses(raw)
    if not clauses:
        return None
    steps: list[dict[str, Any]] = []
    for clause in clauses:
        step = _clause_to_step(clause)
        if step is None:
            # 任一段解析失败 → 不走多步，避免半吊子结果
            return None
        steps.append(step)
        if len(steps) >= MAX_MULTI_STEPS:
            break
    if len(steps) < 2:
        return None
    return steps
