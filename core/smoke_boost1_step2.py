# -*- coding: utf-8 -*-
"""补强包一 · 步骤 2：引擎按场景物体位置示意。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from core.planar_aim import apply_scene_aim_to_task, joints_toward_xy
    from core.pose_grounding_contract import (
        POSE_SOURCE_NONE,
        POSE_SOURCE_SCENE,
        has_forged_object_pose,
    )
    from core.schemas import TaskSpec
    from plugins.engines.mock_engine import MockEngine
    from plugins.engines.mujoco_engine import MujocoEngine

    j = joints_toward_xy(0.36, 0.18)
    assert j is not None and len(j) == 2
    assert j != [0.8, -0.6]

    spec = TaskSpec(task_id="a", action="grab", target="block")
    t2, pose = apply_scene_aim_to_task(
        spec, has_scene=True, object_xpos=[0.36, 0.18, 0.04]
    )
    assert pose["pose_source"] == POSE_SOURCE_SCENE
    assert t2.params.get("joint_targets") == j
    t3, pose_n = apply_scene_aim_to_task(spec, has_scene=False, object_xpos=[0.36, 0.18, 0.04])
    assert pose_n["pose_source"] == POSE_SOURCE_NONE
    assert pose_n["object_xpos"] is None
    assert t3.params.get("joint_targets") is None

    mock = MockEngine()
    mock.load("default")
    r0 = mock.run_task(TaskSpec(task_id="m0", action="grab", target="cup"))
    assert r0.metrics.get("pose_source") == POSE_SOURCE_NONE
    assert not has_forged_object_pose(r0.metrics, has_scene=False)

    mock.load("builtin_arm2_contact")
    r1 = mock.run_task(
        TaskSpec(
            task_id="m1",
            action="grab",
            target="block",
            params={"mock_object_xpos": [0.30, 0.10, 0.04]},
        )
    )
    assert r1.metrics.get("pose_source") == POSE_SOURCE_SCENE
    assert r1.metrics.get("object_xpos") is not None

    mj = MujocoEngine()
    mj.load("default")
    d0 = mj.run_task(TaskSpec(task_id="j0", action="grab", target="cup"))
    assert d0.ok
    assert d0.metrics.get("pose_source") == POSE_SOURCE_NONE
    assert d0.metrics.get("object_xpos") is None

    mj.load("builtin_arm2_contact")
    d1 = mj.run_task(TaskSpec(task_id="j1", action="grab", target="block", params={"steps": 8}))
    assert d1.ok
    assert d1.metrics.get("pose_source") == POSE_SOURCE_SCENE
    assert d1.metrics.get("object_xpos") is not None
    assert d1.metrics.get("ee_goal_xy") is not None
    # 朝物体去：末端不应停在全零
    last = (d1.trajectory or [{}])[-1].get("joint_positions") or []
    assert last and any(abs(float(x)) > 0.05 for x in last[:2])

    d_home = mj.run_task(TaskSpec(task_id="j2", action="home", target=""))
    assert d_home.metrics.get("pose_source") == POSE_SOURCE_NONE

    print("SMOKE_BOOST1_STEP2_OK")


if __name__ == "__main__":
    main()
