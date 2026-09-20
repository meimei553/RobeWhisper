# -*- coding: utf-8 -*-
"""
动作表白名单（第 14 期 · 步骤 1）

产品级唯一来源：解析 / Prompt / 文档应对齐本模块。
教学试机向；不表示工业工艺动作全集。
"""

from __future__ import annotations

from typing import Any

# 旧四动作 + 本期新增 wait（短暂停顿示意；引擎执行留给后续步骤）
ACTION_GRAB = "grab"
ACTION_PLACE = "place"
ACTION_MOVE = "move"
ACTION_HOME = "home"
ACTION_WAIT = "wait"

ALLOWED_ACTIONS = frozenset(
    {
        ACTION_GRAB,
        ACTION_PLACE,
        ACTION_MOVE,
        ACTION_HOME,
        ACTION_WAIT,
    }
)

# 供 Prompt 拼接
ALLOWED_ACTIONS_TEXT = ", ".join(sorted(ALLOWED_ACTIONS))


def action_catalog_rows() -> list[dict[str, Any]]:
    """
    动作表行：中文名 / 键 / 是否通常需要 target / 备注。
    供文档与网站说明复用。
    """
    return [
        {
            "action": ACTION_GRAB,
            "name_zh": "抓",
            "needs_target": True,
            "note": "抓取示意；接触场景下可看接触代理，非工业夹稳",
        },
        {
            "action": ACTION_PLACE,
            "name_zh": "放",
            "needs_target": True,
            "note": "放置示意",
        },
        {
            "action": ACTION_MOVE,
            "name_zh": "移",
            "needs_target": False,
            "note": "小幅关节运动示意",
        },
        {
            "action": ACTION_HOME,
            "name_zh": "回零",
            "needs_target": False,
            "note": "回到初始姿态",
        },
        {
            "action": ACTION_WAIT,
            "name_zh": "等待",
            "needs_target": False,
            "note": "短暂停顿（试机节拍）；第14期新增",
        },
    ]


def is_allowed_action(action: str | None) -> bool:
    return str(action or "").strip().lower() in ALLOWED_ACTIONS


def action_label_zh(action: str | None) -> str:
    key = str(action or "").strip().lower()
    for row in action_catalog_rows():
        if row["action"] == key:
            return str(row["name_zh"])
    return key or "（空）"
