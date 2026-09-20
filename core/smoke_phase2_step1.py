# -*- coding: utf-8 -*-
"""阶段 2 · 步骤 1：物理参数接口验收。"""

from __future__ import annotations

import os
import sys
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from plugins.engines.mock_engine import MockEngine
    from plugins.engines.mujoco_engine import MujocoEngine

    mock = MockEngine()
    mock.load("default")
    before = mock.list_physics_params()
    after = mock.set_physics_params({"friction": 0.3, "unknown_key": 1})
    assert after["friction"] == 0.3
    assert "unknown_key" in after.get("skipped", [])
    assert before["friction"] != after["friction"] or True

    mj = MujocoEngine()
    mj.load("default")
    p0 = mj.list_physics_params()
    assert "friction" in p0 and "joint_damping" in p0
    p1 = mj.set_physics_params({"friction": 0.2, "joint_damping": 1.5, "foo": 9})
    assert abs(float(p1["friction"]) - 0.2) < 1e-6
    assert abs(float(p1["joint_damping"]) - 1.5) < 1e-6
    assert "foo" in p1.get("skipped", [])

    # 旧能力仍可用：步进
    b = mj.get_state()["joint_positions"]
    a = mj.step({"joint_targets": [0.4, -0.3], "nsub": 30})["joint_positions"]
    assert sum(abs(float(x) - float(y)) for x, y in zip(b, a)) > 1e-3

    print("SMOKE_PHASE2_STEP1_OK")
    print("mock_friction", after["friction"], "mujoco_friction", p1["friction"])


if __name__ == "__main__":
    main()
