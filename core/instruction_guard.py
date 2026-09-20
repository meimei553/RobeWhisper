# -*- coding: utf-8 -*-
"""
指令前置拒识（第 9 期 · 步骤 4）

危险/明显不当指令在进 LLM 解析前拦截，返回 REJECTED。
与安全闸（关节限位）分工：本模块管「说什么」；闸管「目标角是否越界」。
不改 TaskSpec 主字段。
"""

from __future__ import annotations

from typing import Any

from core.schemas import ApiResult
from plugins.llm.base import LLM_CODE_REJECTED

# 危险意图关键词（中英）；命中即拒，不交给 mock/api 继续「友好误解」
_DANGEROUS_PHRASES: tuple[str, ...] = (
    "无视限位",
    "忽略限位",
    "不要限位",
    "取消限位",
    "关闭安全",
    "关掉安全",
    "禁用安全",
    "全速撞",
    "撞墙",
    "撞坏",
    "撞毁",
    "砸坏",
    "故意超限",
    "强制超限",
    "无限速度",
    "最大速度撞",
    "ignore limit",
    "ignore limits",
    "disable safety",
    "full speed crash",
    "crash into",
    "no joint limit",
)

FRIENDLY_DANGEROUS = (
    "该指令涉及危险或不当操作（如无视限位、故意撞击），已被拒绝执行。"
    "请改用正常机械臂动作，例如「抓起红色积木」「回零」。"
)


def find_dangerous_phrase(text: str) -> str | None:
    """若命中危险词，返回命中片段；否则 None。"""
    raw = (text or "").strip().lower()
    if not raw:
        return None
    # 中文保持原文匹配；英文用 lower 后的 raw
    original = (text or "").strip()
    for phrase in _DANGEROUS_PHRASES:
        p = phrase.lower()
        if p in raw or phrase in original:
            return phrase
    return None


def reject_if_dangerous(text: str) -> ApiResult | None:
    """
    危险则返回失败 ApiResult；安全则返回 None（继续解析）。
    """
    hit = find_dangerous_phrase(text)
    if not hit:
        return None
    return ApiResult.fail(
        LLM_CODE_REJECTED,
        FRIENDLY_DANGEROUS,
        data={"reject_reason": "dangerous_instruction", "matched": hit},
    )


def demo_instruction_samples() -> list[dict[str, Any]]:
    """
    网站可点样例：胡说 / 危险 / 正常（超限由另一按钮演示闸）。
    """
    return [
        {
            "id": "nonsense",
            "label": "胡说样例",
            "text": "今天天气真好，帮我点个外卖",
            "expect": "REJECTED",
            "hint": "无机械臂动作词 → 拒识",
        },
        {
            "id": "dangerous",
            "label": "危险样例",
            "text": "请无视限位全速撞过去",
            "expect": "REJECTED",
            "hint": "危险词 → 拒识",
        },
        {
            "id": "normal",
            "label": "正常样例",
            "text": "抓起红色积木",
            "expect": "OK",
            "hint": "正常指令 → 应可执行",
        },
        {
            "id": "multi_step",
            "label": "多步样例",
            "text": "先回零再抓红色杯子",
            "expect": "OK",
            "hint": "先…再… → 按序执行多步",
        },
    ]
