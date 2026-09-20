# -*- coding: utf-8 -*-
"""阶段 3 · 步骤 2：Prompt + JSON 校验验收。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from plugins.llm.json_extract import parse_model_text_to_task
    from plugins.llm.mock_llm import MockLLM
    from plugins.llm.prompt import SYSTEM_PROMPT, ALLOWED_ACTIONS_TEXT
    from core.schemas import TaskSpec

    assert "只输出一个 JSON" in SYSTEM_PROMPT or "只输出一个 JSON 对象" in SYSTEM_PROMPT
    assert "grab" in ALLOWED_ACTIONS_TEXT

    # 合法中文 → Mock
    mock = MockLLM()
    ok = mock.parse_instruction("把桌上的红色杯子拿起来", "t1")
    assert ok.ok and ok.data["task_spec"]["action"] == "grab"
    assert ok.data["task_spec"]["target"] == "red_cup"

    # 乱码拒绝
    bad = mock.parse_instruction("??????", "t2")
    assert not bad.ok and bad.code == "REJECTED"

    # 合法 JSON（含代码围栏）
    fenced = parse_model_text_to_task(
        '```json\n{"action":"place","target":"sink","constraints":{},"params":{"steps":2}}\n```',
        task_id="t3",
        raw_user="放到水槽",
        source="llm",
    )
    assert fenced.ok and fenced.data["task_spec"]["action"] == "place"

    # 别名归一
    alias = parse_model_text_to_task(
        '{"action":"pick_up","target":"cup","constraints":{},"params":{}}',
        task_id="t4",
        raw_user="拿杯子",
        source="llm",
    )
    assert alias.ok and alias.data["task_spec"]["action"] == "grab"

    # 非法 JSON
    junk = parse_model_text_to_task("这不是json", task_id="t5", raw_user="拿杯子", source="llm")
    assert not junk.ok and junk.code == "PARSE_FAILED"

    # 不支持动作
    weird = parse_model_text_to_task(
        '{"action":"explode","target":"x","constraints":{},"params":{}}',
        task_id="t6",
        raw_user="爆炸",
        source="llm",
    )
    assert not weird.ok and weird.code == "REJECTED"

    # 危险 params 被剥离后仍可成功（action 合法）
    risky = parse_model_text_to_task(
        '{"action":"move","target":"","constraints":{},"params":{"steps":2,"api_key":"secret","cmd":"rm -rf"}}',
        task_id="t7",
        raw_user="移动一下",
        source="llm",
    )
    assert risky.ok
    assert "api_key" not in risky.data["task_spec"]["params"]
    assert "cmd" not in risky.data["task_spec"]["params"]

    assert set(TaskSpec(task_id="a", action="m").to_dict()) == {
        "task_id",
        "action",
        "target",
        "constraints",
        "params",
        "source",
        "raw_text",
        "steps",
    }

    print("SMOKE_PHASE3_STEP2_OK")
    print("grab_target", ok.data["task_spec"]["target"], "alias", alias.data["task_spec"]["action"])


if __name__ == "__main__":
    main()
