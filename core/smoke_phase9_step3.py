# -*- coding: utf-8 -*-
"""第 9 期 · 步骤 3：仿真墙钟超时验收。"""

from __future__ import annotations

import os
import sys
import time
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
    os.environ["ENGINE_TIMEOUT_SEC"] = "30"

    import config.settings as settings_mod
    import core.bootstrap as bootstrap
    import core.pipeline as pipeline_mod
    import core.engine_timeout as timeout_mod

    reload(settings_mod)
    reload(timeout_mod)
    reload(bootstrap)
    reload(pipeline_mod)

    from core.bootstrap import create_engine, create_llm, create_robot
    from core.engine_timeout import (
        ENGINE_TIMEOUT_CODE,
        FRIENDLY_ENGINE_TIMEOUT,
        resolve_engine_timeout_sec,
    )
    from core.pipeline import Pipeline
    from core.schemas import TaskSpec
    from plugins.engines.mock_engine import MockEngine

    # 误配 ≤0 → 回退 30（避免永远立即超时）
    os.environ["ENGINE_TIMEOUT_SEC"] = "0"
    reload(settings_mod)
    reload(timeout_mod)
    assert resolve_engine_timeout_sec({}) == 30.0

    # params.timeout_sec 只能更严，不能放宽
    os.environ["ENGINE_TIMEOUT_SEC"] = "30"
    reload(settings_mod)
    reload(timeout_mod)
    assert resolve_engine_timeout_sec({"timeout_sec": 5}) == 5.0
    assert resolve_engine_timeout_sec({"timeout_sec": 999}) == 30.0

    # 慢引擎 + 短超时 → ENGINE_TIMEOUT，不抛栈
    class SlowMock(MockEngine):
        def step(self, control):
            time.sleep(0.12)
            return super().step(control)

    slow = SlowMock()
    slow.load("builtin_mock_arm")
    task = TaskSpec(
        task_id="t_timeout",
        action="move",
        params={"steps": 8, "timeout_sec": 0.2, "joint_delta": 0.05},
    )
    sim = slow.run_task(task)
    assert not sim.ok, sim.to_dict()
    assert (sim.metrics or {}).get("timed_out") is True
    assert sim.message == FRIENDLY_ENGINE_TIMEOUT

    # Pipeline 映射错误码：慢引擎 + 更严 timeout_sec
    pipe = Pipeline(llm=create_llm(), engine=slow, robot=create_robot())
    r_fast = Pipeline(llm=create_llm(), engine=create_engine(), robot=create_robot()).run_instruction(
        "回零", real_sim_real=False, save_data=False
    )
    assert r_fast.ok, r_fast.to_dict()

    from unittest.mock import patch

    original_parse = pipe._llm.parse_instruction

    def parse_with_timeout(text: str, task_id: str):
        result = original_parse(text, task_id=task_id)
        if result.ok and result.data and result.data.get("task_spec"):
            params = dict(result.data["task_spec"].get("params") or {})
            params["timeout_sec"] = 0.15
            params["steps"] = 10
            result.data["task_spec"]["params"] = params
        return result

    with patch.object(pipe._llm, "parse_instruction", side_effect=parse_with_timeout):
        r_to = pipe.run_instruction("回零", real_sim_real=False, save_data=False)
    assert not r_to.ok
    assert r_to.code == ENGINE_TIMEOUT_CODE
    assert "超时" in (r_to.message or "")

    # 契约主字段未改
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

    # 恢复默认超时，避免污染
    os.environ["ENGINE_TIMEOUT_SEC"] = "30"
    reload(settings_mod)

    print("SMOKE_PHASE9_STEP3_OK", "timeout", ENGINE_TIMEOUT_CODE, "normal_ok", r_fast.ok)


if __name__ == "__main__":
    main()
