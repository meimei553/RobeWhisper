# -*- coding: utf-8 -*-
"""
第 11 期总复验：步骤 1–4 + 红线检查 + 关键回归。

用法：python -m core.smoke_phase11
"""

from __future__ import annotations

import inspect
import os
import subprocess
import sys
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
    """正式流程第二节：绝不堵死 12–15。"""
    os.environ["USE_REAL_ROBOT"] = "false"
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["LLM_BACKEND"] = "mock"
    os.environ["ENGINE_BACKEND"] = "mujoco"
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)

    from core.robot_bridge_contract import OPTIONAL_TRAJECTORY_KEY, task_spec_main_fields
    from core.schemas import ApiResult, SimResult, TaskSpec
    from plugins.robot.base import BaseRobot
    from plugins.robot.http_robot import HttpRobot
    from plugins.robot.mock_robot import MockRobot
    from plugins.robot.ros_robot import RosRobot

    # 1) 主字段名未改
    assert task_spec_main_fields() == {
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

    # 2) 送单窗口未拆
    for cls in (MockRobot, HttpRobot, RosRobot):
        assert "task" in inspect.signature(cls.execute_task).parameters
    assert issubclass(MockRobot, BaseRobot)

    # 3) 默认关真发 → Mock
    assert bool(settings_mod.USE_REAL_ROBOT) is False
    assert isinstance(bootstrap.create_robot(), MockRobot)

    # 4) 实验旁路可写 robot_result（模块存在）
    from core.experiment_store import build_experiment_record

    rec = build_experiment_record(
        raw_text="t",
        task_spec=TaskSpec(task_id="a", action="home").to_dict(),
        sim_result=SimResult(task_id="a", ok=True).to_dict(),
        ok=True,
        robot_result={"ok": True, "code": "OK", "message": "x", "data": {}},
    )
    assert "robot_result" in rec
    assert set(rec["task_spec"].keys()) == task_spec_main_fields()

    # 5) trajectory 可选扩展点仍在
    assert OPTIONAL_TRAJECTORY_KEY == "trajectory"
    ack_src = (_ROOT / "core" / "robot_bridge_contract.py").read_text(encoding="utf-8")
    assert "trajectory" in ack_src

    # 6) 未做接触抓取裁判 / steps 多步主货币
    pipe_src = (_ROOT / "core" / "pipeline.py").read_text(encoding="utf-8")
    assert "grasp_success" not in pipe_src
    assert "steps[]" not in pipe_src
    # TaskSpec.steps 可选；缺省空列表=单步兼容（第14期）
    assert "steps" in task_spec_main_fields()
    assert TaskSpec(task_id="t", action="home", target="").steps == []

    # 7) 未做 3D / 公网部署硬编码 / 强制 Kimi
    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    assert "pyvista" not in app.lower()
    assert "streamlit.io" not in app.lower()
    assert "USE_REAL_ROBOT" in app
    assert "probe_http_bridge" in app
    assert "real_robot_safety_banner" in app or "真机发送" in app

    # 8) Pipeline 主链：闸 → run_task →（可选）execute_task
    assert "apply_safety_gate" in pipe_src
    assert pipe_src.index("apply_safety_gate") < pipe_src.index("run_task(spec)")
    assert "execute_task" in pipe_src

    # 假接收端与清单存在
    assert (_ROOT / "plugins" / "robot" / "local_fake_receiver.py").exists()
    checklist = (_ROOT / "plugins" / "robot" / "真机联调检查清单.txt").read_text(encoding="utf-8")
    assert "接入真机" in checklist
    assert "task_spec" in checklist


def _check_feature_surface() -> None:
    """核验网站/产品面：用户此前成熟产品所需能力仍在。"""
    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    panel = (_ROOT / "frontend" / "capability_panel.py").read_text(encoding="utf-8")

    must = [
        ("自然语言/对话", "chat_input" in app or "chat_message" in app),
        ("能力边界诊断", "capability_markdown" in app and "diagnose_run_result" in app),
        ("安全样例", "demo_instruction_samples" in app or "demo_sample_" in app),
        ("超限闸演示", "overlimit" in app.lower() or "超限闸" in app),
        ("演示包导出", "demo_pack" in app or "export_demo_pack" in app),
        ("实验浏览", "experiments_table_rows" in app),
        ("经验浏览", "experiences_table_rows" in app),
        ("真发警示", "真机发送" in app or "real_robot_safety_banner" in panel),
        ("HTTP 自检", "自检 HTTP 桥是否通" in app),
        ("RSR 可选", "rsr_enable_ui" in app or "Real-Sim-Real" in app),
    ]
    missing = [name for name, ok in must if not ok]
    assert not missing, f"功能面缺失: {missing}"


def main() -> None:
    for rel in (
        "core/robot_bridge_contract.py",
        "core/robot_bridge_probe.py",
        "plugins/robot/local_fake_receiver.py",
        "plugins/robot/真机联调检查清单.txt",
        "core/smoke_phase11_step1.py",
        "core/smoke_phase11_step2.py",
        "core/smoke_phase11_step3.py",
        "core/smoke_phase11_step4.py",
        "core/阶段11_正式流程_真机最小联调.txt",
    ):
        assert (_ROOT / rel).exists(), rel

    for mod in (
        "core.smoke_phase11_step1",
        "core.smoke_phase11_step2",
        "core.smoke_phase11_step3",
        "core.smoke_phase11_step4",
    ):
        _run_module(mod)

    _check_red_lines()
    _check_feature_surface()

    # 关键回归：9/10 与真机相关
    for mod in (
        "core.smoke_phase9",
        "core.smoke_phase10_step1",
        "core.smoke_phase10_step2",
        "core.smoke_phase5_step2",
        "core.smoke_phase5_step4",
        "core.smoke_phase7_step4",
    ):
        _run_module(mod)

    # 默认配置端到端（关真发）
    os.environ["ENGINE_BACKEND"] = "mujoco"
    os.environ["LLM_BACKEND"] = "mock"
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    os.environ["USE_REAL_SIM_REAL"] = "false"
    os.environ["SAFETY_MODE"] = "clip"
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)
    pipe = bootstrap.create_pipeline()
    result = pipe.run_instruction("抓起红色积木", real_sim_real=False, save_data=True)
    assert result.ok, result.to_dict()
    data = result.data or {}
    assert "task_spec" in data and "sim_result" in data
    assert "robot_result" in data
    exp = data.get("experiment") or {}
    assert exp.get("experiment_id")

    try:
        with urllib.request.urlopen("http://127.0.0.1:8501", timeout=5) as resp:
            assert resp.status == 200
        site = "UP"
    except Exception:
        site = "DOWN"

    print(
        "PHASE11_ACCEPTANCE_PASS",
        "site",
        site,
        "red_lines",
        "ok",
        "features",
        "ok",
        "not_blocking_12_15",
        "ok",
    )


if __name__ == "__main__":
    main()
