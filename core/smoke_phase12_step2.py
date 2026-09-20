# -*- coding: utf-8 -*-
"""第 12 期 · 步骤 2：假接收端可选回传轨迹 → RSR 真轨迹来源。"""

from __future__ import annotations

import os
import sys
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from core.rsr_loop import extract_real_trajectory, is_qualified_real_trajectory, run_rsr_iteration
    from core.schemas import TaskSpec
    from plugins.robot.http_robot import HttpRobot
    from plugins.robot.local_fake_receiver import (
        build_demo_robot_trajectory,
        start_server,
    )

    # 造轨形状合格
    demo = build_demo_robot_trajectory(
        {"task_spec": {"suggested_joint_targets": [0.2, -0.1, 0.05]}},
        frames=3,
    )
    ok, clean, _ = is_qualified_real_trajectory(demo)
    assert ok and len(clean) == 3

    # —— 默认模式：不回轨迹（第11期兼容）——
    srv0, _, h0 = start_server(host="127.0.0.1", port=0, daemon_thread=True, with_trajectory=False)
    try:
        ep0 = f"http://127.0.0.1:{int(srv0.server_address[1])}/execute_task"
        r0 = HttpRobot(endpoint=ep0, timeout_sec=3).execute_task(
            TaskSpec(task_id="n0", action="home", target="")
        )
        assert r0.ok, r0.to_dict()
        ack0 = (r0.data or {}).get("ack") or {}
        assert "trajectory" not in ack0 or not ack0.get("trajectory")
        assert extract_real_trajectory(r0.to_dict()) == []
    finally:
        srv0.shutdown()
        srv0.server_close()

    # —— 带轨迹模式：HttpRobot → 提取合格 → RSR reference_source=robot ——
    srv, _, handler = start_server(
        host="127.0.0.1", port=0, daemon_thread=True, with_trajectory=True
    )
    port = int(srv.server_address[1])
    endpoint = f"http://127.0.0.1:{port}/execute_task"
    try:
        robot = HttpRobot(endpoint=endpoint, timeout_sec=3)
        task = TaskSpec(
            task_id="t12",
            action="grab",
            target="cup",
            params={},
        )
        # suggested_joint_targets 若在 params 而非顶层：造轨仍有默认维
        rr = robot.execute_task(task)
        assert rr.ok, rr.to_dict()
        ack = (rr.data or {}).get("ack") or {}
        assert isinstance(ack.get("trajectory"), list) and ack["trajectory"]
        assert "演示轨迹" in str(ack.get("message") or "")

        rr_dict = rr.to_dict()
        real = extract_real_trajectory(rr_dict)
        assert len(real) >= 1

        class _FakeEng:
            def list_physics_params(self) -> dict:
                return {"friction": 0.5, "joint_damping": 0.1}

            def set_physics_params(self, **kwargs) -> None:
                return None

        sim = [
            {"t": 0.0, "joint_positions": [0.0, 0.0]},
            {"t": 1.0, "joint_positions": [0.1, 0.1]},
            {"t": 2.0, "joint_positions": [0.2, 0.2]},
            {"t": 3.0, "joint_positions": [0.3, 0.3]},
        ]
        rsr = run_rsr_iteration(_FakeEng(), sim, rr_dict, allow_pseudo_real=True)
        assert rsr.get("reference_source") == "robot", rsr
        assert rsr.get("skipped") is False

        # Pipeline：真发 + 带轨迹假接收端 + 开 RSR → robot
        os.environ["ENGINE_BACKEND"] = "mujoco"
        os.environ["LLM_BACKEND"] = "mock"
        os.environ["ROBOT_BACKEND"] = "http"
        os.environ["USE_REAL_ROBOT"] = "true"
        os.environ["ROBOT_EXECUTE_ENDPOINT"] = endpoint
        os.environ["USE_REAL_SIM_REAL"] = "false"
        import config.settings as settings_mod
        import core.bootstrap as bootstrap

        reload(settings_mod)
        reload(bootstrap)
        from core.bootstrap import create_engine, create_llm, create_robot
        from core.pipeline import Pipeline

        pipe = Pipeline(llm=create_llm(), engine=create_engine(), robot=create_robot())
        out = pipe.run_instruction("抓起红色积木", real_sim_real=True)
        assert out.ok, out.to_dict()
        rsr2 = (out.data or {}).get("rsr") or {}
        assert rsr2.get("reference_source") == "robot", rsr2
        assert (out.data or {}).get("robot_result", {}).get("ok") is True
    finally:
        srv.shutdown()
        srv.server_close()
        os.environ["ROBOT_BACKEND"] = "mock"
        os.environ["USE_REAL_ROBOT"] = "false"
        os.environ["ROBOT_EXECUTE_ENDPOINT"] = ""
        import config.settings as settings_mod
        import core.bootstrap as bootstrap

        reload(settings_mod)
        reload(bootstrap)

    # CLI 帮助含开关
    src = (_ROOT / "plugins" / "robot" / "local_fake_receiver.py").read_text(encoding="utf-8")
    assert "--with-trajectory" in src
    assert "with_trajectory" in src

    print("SMOKE_PHASE12_STEP2_OK")


if __name__ == "__main__":
    main()
