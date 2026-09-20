# -*- coding: utf-8 -*-
"""
阶段 1 · 步骤 3：MuJoCo 适配器命令行验收（无前端）。

用法（项目根目录）：
  python -m core.smoke_mujoco_step3
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from core.schemas import TaskSpec
    from plugins.engines.base import BaseEngine
    from plugins.engines.mujoco_engine import MujocoEngine

    engine: BaseEngine = MujocoEngine()
    engine.load("default")
    engine.reset()
    before = engine.get_state()["joint_positions"]

    after = engine.step(
        {
            "action": "move",
            "joint_targets": [0.7, -0.5],
            "nsub": 40,
        }
    )["joint_positions"]

    assert len(before) >= 2 and len(after) >= 2
    delta = sum(abs(float(a) - float(b)) for a, b in zip(before, after))
    assert delta > 1e-3, f"关节角未明显变化 before={before} after={after}"

    result = engine.run_task(
        TaskSpec(
            task_id="smoke3",
            action="grab",
            target="red_cup",
            params={"steps": 4, "nsub": 30},
            source="mock",
        )
    )
    assert result.ok, result.message
    assert result.engine_name == "mujoco_engine"
    assert len(result.trajectory) >= 2

    # bootstrap 切换
    os.environ["ENGINE_BACKEND"] = "mujoco"
    # settings 在 import 时已读环境；这里直接测工厂逻辑
    from importlib import reload
    import config.settings as settings_mod

    reload(settings_mod)
    from core import bootstrap

    reload(bootstrap)
    eng2 = bootstrap.create_engine()
    assert isinstance(eng2, MujocoEngine)

    os.environ["ENGINE_BACKEND"] = "mock"
    reload(settings_mod)
    reload(bootstrap)
    eng3 = bootstrap.create_engine()
    from plugins.engines.mock_engine import MockEngine

    assert isinstance(eng3, MockEngine)

    # pipeline 源码不得直接出现 MujocoEngine（组装只在 bootstrap）
    pipe_src = (_ROOT / "core/pipeline.py").read_text(encoding="utf-8")
    assert "MujocoEngine" not in pipe_src
    app_src = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    assert "import mujoco" not in app_src

    print("before", before)
    print("after", after)
    print("delta", delta)
    print("SMOKE_MUJOCO_STEP3_OK")


if __name__ == "__main__":
    main()
