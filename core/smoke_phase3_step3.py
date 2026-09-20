# -*- coding: utf-8 -*-
"""阶段 3 · 步骤 3：自然语言 → TaskSpec → 引擎执行 验收。"""

from __future__ import annotations

import os
import sys
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _boot(engine_backend: str, llm_backend: str = "mock"):
    os.environ["ENGINE_BACKEND"] = engine_backend
    os.environ["LLM_BACKEND"] = llm_backend
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)
    return bootstrap


def main() -> None:
    from core.schemas import TaskSpec
    from plugins.engines.mujoco_engine import MujocoEngine
    from plugins.engines.mock_engine import MockEngine

    # 1) Mock LLM + MuJoCo：真实仿真执行
    bootstrap = _boot("mujoco", "mock")
    pipe = bootstrap.create_pipeline()
    assert isinstance(pipe._engine, MujocoEngine)

    ok = pipe.run_instruction("把桌上的红色杯子拿起来")
    assert ok.ok, ok.to_dict()
    assert ok.data["task_spec"]["action"] == "grab"
    assert ok.data["task_spec"]["target"] == "red_cup"
    assert ok.data["adapters"]["engine"] == "mujoco_engine"
    sim = ok.data["sim_result"]
    assert sim["ok"] is True
    assert len(sim.get("trajectory") or []) >= 2
    # 轨迹应有关节运动或至少多帧
    traj = sim["trajectory"]
    moved = False
    if len(traj) >= 2:
        a = traj[0].get("joint_positions") or []
        b = traj[-1].get("joint_positions") or []
        moved = any(abs(float(x) - float(y)) > 1e-4 for x, y in zip(a, b))
    assert moved or sim.get("metrics", {}).get("moved") is True

    # 2) 非法指令：失败但不抛异常
    bad = pipe.run_instruction("??????")
    assert not bad.ok
    assert bad.code in ("REJECTED", "PARSE_FAILED")

    # 3) Mock 引擎回退仍可用
    bootstrap2 = _boot("mock", "mock")
    pipe2 = bootstrap2.create_pipeline()
    assert isinstance(pipe2._engine, MockEngine)
    ok2 = pipe2.run_instruction("回零")
    assert ok2.ok and ok2.data["task_spec"]["action"] == "home"

    # 4) 契约与隔离
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
    pipe_src = (_ROOT / "core/pipeline.py").read_text(encoding="utf-8")
    assert "MujocoEngine" not in pipe_src and "ApiLLM" not in pipe_src

    print("SMOKE_PHASE3_STEP3_OK")
    print("engine", ok.data["adapters"]["engine"], "moved", moved, "frames", len(traj))


if __name__ == "__main__":
    main()
