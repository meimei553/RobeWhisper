# -*- coding: utf-8 -*-
"""第 14 期 · 步骤 2：解析支持多步与新动作。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from core.multi_step_contract import MAX_MULTI_STEPS
    from core.multi_step_parse import try_parse_multi_steps
    from plugins.llm.json_extract import task_spec_from_model_dict
    from plugins.llm.mock_llm import MockLLM

    llm = MockLLM()

    # 旧单步仍通
    r0 = llm.parse_instruction("把红色杯子拿起来", task_id="s0")
    assert r0.ok, r0.to_dict()
    ts0 = r0.data["task_spec"]
    assert ts0["action"] == "grab"
    assert ts0["target"] == "red_cup"
    assert ts0.get("steps") == []

    r_home = llm.parse_instruction("回零", task_id="s1")
    assert r_home.ok
    assert r_home.data["task_spec"]["action"] == "home"
    assert r_home.data["task_spec"].get("steps") == []

    # 新动作 wait
    r_wait = llm.parse_instruction("等待一下", task_id="s2")
    assert r_wait.ok, r_wait.to_dict()
    assert r_wait.data["task_spec"]["action"] == "wait"

    # 多步：先回零再抓
    r_m = llm.parse_instruction("先回零再抓红色杯子", task_id="s3")
    assert r_m.ok, r_m.to_dict()
    ts = r_m.data["task_spec"]
    assert len(ts["steps"]) == 2
    assert ts["steps"][0]["action"] == "home"
    assert ts["steps"][1]["action"] == "grab"
    assert "cup" in ts["steps"][1]["target"] or ts["steps"][1]["target"] == "red_cup"
    assert ts["action"] == "home"  # 摘要取首步

    # 然后
    r_m2 = llm.parse_instruction("回零然后抓起红色积木", task_id="s4")
    assert r_m2.ok, r_m2.to_dict()
    assert len(r_m2.data["task_spec"]["steps"]) == 2

    # 纯函数拆句
    assert try_parse_multi_steps("先回零再抓红色杯子") is not None
    assert try_parse_multi_steps("把红色杯子拿起来") is None

    # JSON 入口：合法多步
    ok = task_spec_from_model_dict(
        {
            "action": "home",
            "target": "",
            "constraints": {},
            "params": {},
            "steps": [
                {"action": "home", "target": ""},
                {"action": "grab", "target": "red_cup", "params": {"steps": 3}},
            ],
        },
        task_id="j1",
        raw_text="先回零再抓",
        source="api",
    )
    assert ok.ok
    assert len(ok.data["task_spec"]["steps"]) == 2

    # 过长拒绝
    too_many = [{"action": "wait", "target": ""} for _ in range(MAX_MULTI_STEPS + 1)]
    bad = task_spec_from_model_dict(
        {"action": "wait", "target": "", "constraints": {}, "params": {}, "steps": too_many},
        task_id="j2",
        raw_text="x",
        source="api",
    )
    assert not bad.ok
    assert "过多" in (bad.message or "") or "5" in (bad.message or "")

    # 非法动作拒识
    bad2 = task_spec_from_model_dict(
        {"action": "fly", "target": "", "constraints": {}, "params": {}},
        task_id="j3",
        raw_text="飞",
        source="api",
    )
    assert not bad2.ok

    # 能力说明提到多步或等待
    doc = (_ROOT / "core" / "自然语言能力说明.txt").read_text(encoding="utf-8")
    assert "wait" in doc or "等待" in doc

    print("SMOKE_PHASE14_STEP2_OK")


if __name__ == "__main__":
    main()
