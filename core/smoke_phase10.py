# -*- coding: utf-8 -*-
"""
第 10 期总复验：步骤 1–4 + 红线检查 + 关键回归 + 第9期烟雾。

用法：python -m core.smoke_phase10
"""

from __future__ import annotations

import inspect
import os
import subprocess
import sys
import tempfile
import urllib.request
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _run_module(mod: str) -> None:
    r = subprocess.run(
        [sys.executable, "-m", mod],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode != 0:
        raise AssertionError(f"{mod} failed:\n{r.stdout}\n{r.stderr}")


def _check_red_lines() -> None:
    """书面第二节「绝不堵死 11–15」的可执行核对。"""
    os.environ["EXPERIENCE_ALLOW_CROSS_MODEL"] = "false"
    import config.settings as settings_mod

    reload(settings_mod)

    from core.experience_store import make_key
    from core.schemas import ApiResult, SimResult, TaskSpec
    from plugins.robot.base import BaseRobot
    from plugins.robot.http_robot import HttpRobot
    from plugins.robot.mock_robot import MockRobot
    from plugins.robot.ros_robot import RosRobot

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
    assert set(SimResult(task_id="a", ok=True).to_dict()) == {
        "task_id",
        "ok",
        "trajectory",
        "metrics",
        "message",
        "engine_name",
        "engine_version",
    }
    assert set(ApiResult.success().to_dict()) == {"ok", "code", "message", "data"}

    for cls in (MockRobot, HttpRobot, RosRobot):
        assert "task" in inspect.signature(cls.execute_task).parameters
    assert issubclass(MockRobot, BaseRobot)

    # 经验：新键带 model；旧键函数仍存在
    assert "__" in make_key("grab", "cup", "arm_a", with_model=True)
    assert make_key("grab", "cup", with_model=False) == "grab__cup"

    assert settings_mod.EXPERIENCE_ALLOW_CROSS_MODEL is False

    # RSR 伪对照仍可关
    rsr_src = (_ROOT / "core" / "rsr_loop.py").read_text(encoding="utf-8")
    assert "allow_pseudo_real" in rsr_src

    # 演示包模块存在且不依赖 Streamlit
    assert (_ROOT / "core" / "demo_pack.py").exists()
    assert (_ROOT / "core" / "run_snapshot.py").exists()

    # 未做 3D / 机械狗 / 多用户云
    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    assert "pyvista" not in app.lower()
    assert "机械狗" not in app
    assert "export_demo_pack" in app or "demo_pack" in app

    # Pipeline 主链：闸 → run_task；经验带 model_ref
    pipe_src = (_ROOT / "core" / "pipeline.py").read_text(encoding="utf-8")
    assert "apply_safety_gate" in pipe_src
    assert pipe_src.index("apply_safety_gate") < pipe_src.index("run_task(spec)")
    assert "model_ref=ref" in pipe_src or "model_ref=ref," in pipe_src

    assert (_ROOT / "models" / "builtin_arm2" / "model.xml").exists()


def main() -> None:
    for rel in (
        "core/run_snapshot.py",
        "core/demo_pack.py",
        "core/experience_store.py",
        "core/experiment_store.py",
        "core/smoke_phase10_step1.py",
        "core/smoke_phase10_step2.py",
        "core/smoke_phase10_step3.py",
        "core/smoke_phase10_step4.py",
        "core/阶段10_正式流程_可复现与经验标签.txt",
        "core/阶段10_步骤1_运行快照验收.txt",
        "core/阶段10_步骤2_实验快照落盘验收.txt",
        "core/阶段10_步骤3_经验模型分区验收.txt",
        "core/阶段10_步骤4_演示包导出验收.txt",
        "core/阶段10验收.txt",
    ):
        assert (_ROOT / rel).exists(), rel

    for mod in (
        "core.smoke_phase10_step1",
        "core.smoke_phase10_step2",
        "core.smoke_phase10_step3",
        "core.smoke_phase10_step4",
    ):
        _run_module(mod)

    _check_red_lines()

    # 关键回归 + 第 9 期总验
    for mod in (
        "core.smoke_phase9",
        "core.smoke_phase4_step2",
        "core.smoke_phase4_step3",
        "core.smoke_phase6_step4",
        "core.smoke_phase7_step2",
    ):
        parts = mod.split(".")
        path = _ROOT.joinpath(*parts[:-1], f"{parts[-1]}.py")
        assert path.exists(), mod
        _run_module(mod)

    # 端到端：落盘含快照 + 演示包
    os.environ["ENGINE_BACKEND"] = "mujoco"
    os.environ["LLM_BACKEND"] = "mock"
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    os.environ["USE_REAL_SIM_REAL"] = "false"
    os.environ["SAFETY_MODE"] = "clip"
    os.environ["EXPERIENCE_ALLOW_CROSS_MODEL"] = "false"
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)
    pipe = bootstrap.create_pipeline()
    result = pipe.run_instruction("回零", real_sim_real=False, save_data=True)
    assert result.ok, result.to_dict()
    exp = (result.data or {}).get("experiment") or {}
    assert exp.get("ok") == "true"
    from pathlib import Path as P

    data = __import__("json").loads(P(exp["path"]).read_text(encoding="utf-8"))
    assert "run_snapshot" in data

    with tempfile.TemporaryDirectory(prefix="rw_p10_") as tmp:
        from core.demo_pack import export_demo_pack

        pack = export_demo_pack(data["experiment_id"], out_dir=P(tmp))
        assert pack.get("ok"), pack

    # 跨臂经验不命中（隔离目录）
    with tempfile.TemporaryDirectory(prefix="rw_p10e_") as tmp_e:
        os.environ["EXPERIENCE_DIR"] = tmp_e
        reload(settings_mod)
        import core.experience_store as exp_mod

        reload(exp_mod)
        exp_mod.remember_experience(
            action="grab",
            target="red_block",
            raw_text="a",
            trajectory=[{"joint_positions": [1.0, 0.0]}],
            ok=True,
            model_ref="arm_a",
        )
        assert exp_mod.find_experience("grab", "red_block", model_ref="arm_b") is None
        assert exp_mod.find_experience("grab", "red_block", model_ref="arm_a") is not None

    try:
        with urllib.request.urlopen("http://127.0.0.1:8501", timeout=5) as resp:
            assert resp.status == 200
        site = "UP"
    except Exception:
        site = "DOWN"

    print("PHASE10_ACCEPTANCE_PASS", "site", site, "red_lines", "ok", "mature_1_10", "ready")


if __name__ == "__main__":
    main()
