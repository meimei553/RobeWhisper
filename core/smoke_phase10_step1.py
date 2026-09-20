# -*- coding: utf-8 -*-
"""第 10 期 · 步骤 1：运行快照纯函数验收。"""

from __future__ import annotations

import json
import os
import sys
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    os.environ["ENGINE_BACKEND"] = "mujoco"
    os.environ["LLM_BACKEND"] = "mock"
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    os.environ["USE_REAL_SIM_REAL"] = "false"
    os.environ["SAFETY_MODE"] = "clip"
    # 故意放一个假 Key 在环境里，快照也不得收录
    os.environ["LLM_API_KEY"] = "sk-test-should-never-appear-in-snapshot"

    import config.settings as settings_mod

    reload(settings_mod)

    from core.run_snapshot import (
        RUN_SNAPSHOT_SCHEMA_VERSION,
        collect_run_snapshot,
        snapshot_contains_secrets,
    )
    from core.schemas import TaskSpec
    from core.bootstrap import create_engine, create_llm, create_robot

    # 缺适配器：仍可读占位
    bare = collect_run_snapshot(model_ref="default")
    assert bare["schema_version"] == RUN_SNAPSHOT_SCHEMA_VERSION
    assert "collected_at" in bare
    assert bare["adapters"]["llm"]["name"]
    assert bare["adapters"]["engine"]["name"]
    assert bare["backends"]["ENGINE_BACKEND"] == "mujoco"
    assert bare["flags"]["SAFETY_MODE"] == "clip"
    assert bare["model_ref"] == "default"
    assert snapshot_contains_secrets(bare) == []

    # 有适配器实例
    llm = create_llm()
    eng = create_engine()
    robot = create_robot()
    full = collect_run_snapshot(
        llm=llm,
        engine=eng,
        robot=robot,
        adapters={"llm": llm.name, "engine": eng.name, "robot": robot.name},
        model_ref="builtin_arm2",
        extra={"note": "demo", "api_key": "sk-leaked", "LLM_API_KEY": "secret"},
    )
    assert full["adapters"]["engine"]["name"] == eng.name
    assert full["model_ref"] == "builtin_arm2"
    assert "api_key" not in (full.get("extra") or {})
    assert "LLM_API_KEY" not in (full.get("extra") or {})
    assert (full.get("extra") or {}).get("note") == "demo"
    assert snapshot_contains_secrets(full) == []

    blob = json.dumps(full, ensure_ascii=False)
    assert "sk-" not in blob.lower()
    assert "LLM_API_KEY" not in blob
    assert "api_key" not in blob.lower()

    # 仅 adapters 字符串、无实例
    named = collect_run_snapshot(adapters={"llm": "mock_llm", "engine": "mujoco_engine", "robot": "mock_robot"})
    assert named["adapters"]["llm"]["name"] == "mock_llm"

    # 不改 TaskSpec 主字段
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

    # 清理测试密钥，避免污染后续
    os.environ.pop("LLM_API_KEY", None)
    reload(settings_mod)

    print(
        "SMOKE_PHASE10_STEP1_OK",
        "schema",
        bare["schema_version"],
        "engine",
        full["adapters"]["engine"]["name"],
        "secrets",
        0,
    )


if __name__ == "__main__":
    main()
