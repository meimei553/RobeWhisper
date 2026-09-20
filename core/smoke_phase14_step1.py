# -*- coding: utf-8 -*-
"""第 14 期 · 步骤 1：动作表 + 多步契约。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from core.action_catalog import (
        ACTION_WAIT,
        ALLOWED_ACTIONS,
        ALLOWED_ACTIONS_TEXT,
        action_catalog_rows,
        is_allowed_action,
    )
    from core.multi_step_contract import (
        MAX_MULTI_STEPS,
        SIM_SUBSTEPS_PARAM_KEY,
        empty_steps,
        is_multi_step,
        normalize_steps,
        primary_action_from_spec,
        sim_substeps_note,
        validate_steps_list,
    )
    from core.schemas import TaskSpec
    from plugins.llm.json_extract import ALLOWED_ACTIONS as JE_ACTIONS
    from plugins.llm.prompt import ALLOWED_ACTIONS_TEXT as PROMPT_ACTIONS

    # 动作表含旧四动作 + wait
    for a in ("grab", "place", "move", "home", "wait"):
        assert a in ALLOWED_ACTIONS
        assert is_allowed_action(a)
    assert ACTION_WAIT == "wait"
    assert not is_allowed_action("fly")
    assert not is_allowed_action("caught_for_factory")
    rows = action_catalog_rows()
    assert len(rows) == 5
    assert any(r["action"] == "wait" for r in rows)

    # 解析层与 Prompt 与目录对齐
    assert JE_ACTIONS == ALLOWED_ACTIONS
    assert "wait" in PROMPT_ACTIONS
    assert set(ALLOWED_ACTIONS_TEXT.replace(" ", "").split(",")) == ALLOWED_ACTIONS

    # 单步兼容：缺省 steps=[]
    d0 = TaskSpec(task_id="t0", action="grab", target="cup").to_dict()
    for k in ("task_id", "action", "target", "constraints", "params", "source", "raw_text", "steps"):
        assert k in d0
    assert d0["steps"] == []
    assert empty_steps() == []
    assert not is_multi_step(d0["steps"])

    # 旧 JSON 无 steps 键仍可 from_dict
    old = TaskSpec.from_dict(
        {"task_id": "old", "action": "home", "target": "", "constraints": {}, "params": {}}
    )
    assert old.steps == []
    assert old.action == "home"

    # 多步规范化
    raw = [
        {"action": "home", "target": ""},
        {"action": "grab", "target": "red_cup", "params": {"steps": 3}},
        {"action": "fly", "target": "x"},  # 非法，跳过
    ]
    steps = normalize_steps(raw)
    assert len(steps) == 2
    assert steps[0]["action"] == "home"
    assert steps[1]["action"] == "grab"
    assert steps[1]["params"].get("steps") == 3
    assert is_multi_step(steps)
    assert validate_steps_list(steps)
    assert not validate_steps_list(steps + [{"action": "bad"}])

    # 上限截断
    many = [{"action": "wait", "target": ""} for _ in range(MAX_MULTI_STEPS + 3)]
    truncated = normalize_steps(many)
    assert len(truncated) == MAX_MULTI_STEPS

    spec = TaskSpec(
        task_id="t1",
        action="home",
        target="",
        steps=steps,
        raw_text="先回零再抓红色杯子",
    )
    assert len(spec.to_dict()["steps"]) == 2
    back = TaskSpec.from_dict(spec.to_dict())
    assert len(back.steps) == 2
    assert primary_action_from_spec(action=spec.action, steps=spec.steps) == "home"

    # 命名区分写进契约说明
    assert SIM_SUBSTEPS_PARAM_KEY == "steps"
    note = sim_substeps_note()
    assert "params" in note and "TaskSpec.steps" in note

    # 书面动作表存在
    doc = _ROOT / "core" / "动作表_第14期.txt"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    assert "wait" in text
    assert "TaskSpec.steps" in text

    print("SMOKE_PHASE14_STEP1_OK")


if __name__ == "__main__":
    main()
