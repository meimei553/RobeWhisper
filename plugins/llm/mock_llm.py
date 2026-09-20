# -*- coding: utf-8 -*-
"""Mock LLM：关键词规则 + 统一走 TaskSpec 校验出口。"""

from __future__ import annotations

import re

from core.schemas import ApiResult
from core.instruction_guard import reject_if_dangerous
from core.multi_step_parse import infer_action, try_parse_multi_steps
from plugins.llm.base import FRIENDLY_BLOCKED, BaseLLM, LLM_CODE_PARSE_FAILED, LLM_CODE_REJECTED
from plugins.llm.json_extract import task_spec_from_model_dict

# 颜色词 → 英文前缀（便于经验库键名稳定）
_COLOR_MAP = (
    ("红色", "red"),
    ("红", "red"),
    ("蓝色", "blue"),
    ("蓝", "blue"),
    ("绿色", "green"),
    ("绿", "green"),
    ("黄色", "yellow"),
    ("黄", "yellow"),
    ("黑色", "black"),
    ("白", "white"),
    ("白色", "white"),
)

# 物体词 → 英文名（可继续加，不必改引擎）
_OBJECT_MAP = (
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


def _infer_target(raw: str) -> str:
    """从中文指令推断 target；没有物体则返回空串。"""
    color = ""
    for cn, en in _COLOR_MAP:
        if cn in raw:
            color = en
            break
    obj = ""
    for cn, en in _OBJECT_MAP:
        if cn in raw:
            obj = en
            break
    if color and obj:
        return f"{color}_{obj}"
    if obj:
        return obj
    # 英文物体兜底
    m = re.search(r"\b(red_|blue_|green_)?(cup|block|bottle|box)\b", raw.lower())
    if m:
        return m.group(0).replace(" ", "_")
    return ""


class MockLLM(BaseLLM):
    """无云端时的本地解析；输出形态与 ApiLLM 一致。"""

    @property
    def name(self) -> str:
        return "mock_llm"

    def parse_instruction(self, text: str, task_id: str) -> ApiResult:
        raw = (text or "").strip()
        if not raw:
            return ApiResult.fail(LLM_CODE_PARSE_FAILED, FRIENDLY_BLOCKED)
        if len(raw) > 500:
            return ApiResult.fail(LLM_CODE_REJECTED, "指令过长，请缩短后再试。")

        # 危险词优先拒识（第 9 期步骤4）；再走关键词解析
        blocked = reject_if_dangerous(raw)
        if blocked is not None:
            return blocked

        # 多步：先…再… / 然后 / 接着
        multi = try_parse_multi_steps(raw)
        if multi is not None:
            first = multi[0]
            return task_spec_from_model_dict(
                {
                    "action": first.get("action", ""),
                    "target": first.get("target", ""),
                    "constraints": {},
                    "params": dict(first.get("params") or {}),
                    "steps": multi,
                },
                task_id=task_id,
                raw_text=raw,
                source="mock",
            )

        action = infer_action(raw) or "move"
        # infer_action 认不出时再走旧关键词（兼容「动一下」等）
        if action == "move" and not any(k in raw for k in ("移", "动", "走", "转")):
            if "拿" in raw or "抓" in raw or "拾" in raw or "夹" in raw:
                action = "grab"
            elif "放" in raw or "放下" in raw or "放到" in raw:
                action = "place"
            elif "回零" in raw or "复位" in raw or "归位" in raw or "home" in raw.lower():
                action = "home"
            elif any(k in raw for k in ("等待", "等一下", "停一下", "停顿")) or "wait" in raw.lower():
                action = "wait"
            elif "移" in raw or "动" in raw or "走" in raw or "转" in raw:
                action = "move"

        target = _infer_target(raw)

        known = any(
            k in raw
            for k in (
                "拿",
                "抓",
                "拾",
                "夹",
                "放",
                "移",
                "动",
                "走",
                "转",
                "回零",
                "复位",
                "归位",
                "home",
                "等待",
                "等一下",
                "停一下",
                "停顿",
                "wait",
            )
        ) or "home" in raw.lower()
        if not known:
            return ApiResult.fail(
                LLM_CODE_REJECTED,
                "暂时无法识别该指令。请带上「抓/拿/放/移/回零/等待」等词，"
                "或在 .env 打开 LLM_BACKEND=api 以理解更自由的说法。",
            )

        # 抓/放必须能认出物体，否则明确提示（避免用户以为“随便说都能抓”）
        if action in {"grab", "place"} and not target:
            return ApiResult.fail(
                LLM_CODE_REJECTED,
                "没有识别到支持的物体名称。"
                "当前可说：杯子、积木、方块、木块、瓶子、盒子、工件、零件"
                "（可加红/蓝/绿/黄/黑/白等颜色，例如「抓起红色积木」）。"
                "若要识别更多说法，请配置 LLM_BACKEND=api，或让协助者在词表中追加物体。",
            )

        params: dict = {"steps": 3, "joint_delta": 0.1}
        if action == "wait":
            params = {"seconds": 0.5}
        elif action == "home":
            params = {}

        return task_spec_from_model_dict(
            {
                "action": action,
                "target": target,
                "constraints": {},
                "params": params,
            },
            task_id=task_id,
            raw_text=raw,
            source="mock",
        )
