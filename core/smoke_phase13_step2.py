# -*- coding: utf-8 -*-
"""第 13 期 · 步骤 2：引擎接触/接近度量。"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from core.contact_probe import build_contact_metrics, decide_grasp_proxy
    from core.contact_scene_contract import (
        GRASP_PROXY_NO_CONTACT,
        GRASP_PROXY_NO_SCENE,
        GRASP_PROXY_OK,
        GRASP_PROXY_UNCERTAIN,
    )
    from core.schemas import TaskSpec
    from plugins.engines.mock_engine import MockEngine
    from plugins.engines.mujoco_engine import MujocoEngine

    # —— 纯函数决策 ——
    assert decide_grasp_proxy(
        has_scene=False, action="grab", contact_detected=False, object_moved=False, ee_object_distance=None
    ) == GRASP_PROXY_NO_SCENE
    assert (
        decide_grasp_proxy(
            has_scene=True, action="grab", contact_detected=True, object_moved=False, ee_object_distance=0.05
        )
        == GRASP_PROXY_OK
    )
    assert (
        decide_grasp_proxy(
            has_scene=True, action="grab", contact_detected=False, object_moved=False, ee_object_distance=0.50
        )
        == GRASP_PROXY_NO_CONTACT
    )
    assert (
        decide_grasp_proxy(
            has_scene=True, action="grab", contact_detected=False, object_moved=False, ee_object_distance=0.09
        )
        == GRASP_PROXY_UNCERTAIN
    )

    # —— Mock：三种可预测结果 ——
    mock = MockEngine()
    mock.load("builtin_mock_arm")
    r0 = mock.run_task(TaskSpec(task_id="m0", action="grab", target="x"))
    assert r0.metrics.get("grasp_proxy") == GRASP_PROXY_NO_SCENE
    assert r0.metrics.get("contact_scene") is False

    mock.load("builtin_arm2_contact")
    r_ok = mock.run_task(
        TaskSpec(task_id="m1", action="grab", target="block", params={"mock_grasp_proxy": "ok"})
    )
    assert r_ok.metrics.get("grasp_proxy") == GRASP_PROXY_OK
    assert r_ok.metrics.get("contact_detected") is True

    r_nc = mock.run_task(
        TaskSpec(task_id="m2", action="grab", target="block", params={"mock_grasp_proxy": "no_contact"})
    )
    assert r_nc.metrics.get("grasp_proxy") == GRASP_PROXY_NO_CONTACT

    # —— MuJoCo：默认臂无场景 ——
    mj = MujocoEngine()
    mj.load("default")
    d0 = mj.run_task(TaskSpec(task_id="j0", action="grab", target="cup"))
    assert d0.ok
    assert d0.metrics.get("grasp_proxy") == GRASP_PROXY_NO_SCENE
    assert d0.metrics.get("contact_scene") is False

    # —— MuJoCo：接触场景 + home → 通常无抓取接触 ——
    mj.load("builtin_arm2_contact")
    d_home = mj.run_task(TaskSpec(task_id="j1", action="home", target=""))
    assert d_home.ok
    assert d_home.metrics.get("contact_scene") is True
    assert d_home.metrics.get("grasp_proxy") in {
        GRASP_PROXY_NO_CONTACT,
        GRASP_PROXY_UNCERTAIN,
    }
    assert d_home.metrics.get("grasp_proxy") != GRASP_PROXY_OK

    # —— MuJoCo：接触场景 + grab → 应能接触或至少接近（proxy≠no_scene）——
    mj.reset()
    d_grab = mj.run_task(
        TaskSpec(task_id="j2", action="grab", target="block", params={"steps": 8})
    )
    assert d_grab.ok
    assert d_grab.metrics.get("contact_scene") is True
    assert d_grab.metrics.get("grasp_proxy") in {
        GRASP_PROXY_OK,
        GRASP_PROXY_UNCERTAIN,
        GRASP_PROXY_NO_CONTACT,
    }
    # 期望默认抓姿能碰到/靠近：若仍 no_contact，用显式目标再逼近一次
    if d_grab.metrics.get("grasp_proxy") == GRASP_PROXY_NO_CONTACT:
        mj.reset()
        d_grab2 = mj.run_task(
            TaskSpec(
                task_id="j3",
                action="grab",
                target="block",
                params={"joint_targets": [0.75, -0.55], "steps": 10},
            )
        )
        assert d_grab2.metrics.get("grasp_proxy") in {
            GRASP_PROXY_OK,
            GRASP_PROXY_UNCERTAIN,
        }, d_grab2.metrics
        assert d_grab2.metrics.get("ee_object_distance") is not None

    # 显式远离：应 no_contact
    mj.reset()
    d_far = mj.run_task(
        TaskSpec(
            task_id="j4",
            action="grab",
            target="block",
            params={"joint_targets": [0.0, 0.0], "steps": 4},
        )
    )
    assert d_far.metrics.get("contact_scene") is True
    assert d_far.metrics.get("grasp_proxy") in {
        GRASP_PROXY_NO_CONTACT,
        GRASP_PROXY_UNCERTAIN,
    }
    # 零位通常够远
    if d_far.metrics.get("ee_object_distance") is not None:
        assert float(d_far.metrics["ee_object_distance"]) > 0.12

    # build_contact_metrics 键齐全
    m = build_contact_metrics(has_scene=True, action="grab", contact_detected=True)
    for k in ("contact_scene", "contact_detected", "grasp_proxy", "object_moved", "ee_object_distance"):
        assert k in m

    print("SMOKE_PHASE13_STEP2_OK", "grab_proxy", d_grab.metrics.get("grasp_proxy"))


if __name__ == "__main__":
    main()
