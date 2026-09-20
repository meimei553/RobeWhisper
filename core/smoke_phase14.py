# -*- coding: utf-8 -*-
"""
第 14 期总复验：步骤 1–4 + 档 A 功能清单 + 硬约束 + 相关回归。

用法：python -m core.smoke_phase14
期望：PHASE14_ACCEPTANCE_PASS
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _run_module(mod: str) -> str:
    r = subprocess.run(
        [sys.executable, "-m", mod],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        raise AssertionError(f"{mod} 失败:\n{out}")
    return out


def _assert_defaults_safe() -> None:
    ex = (_ROOT / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"(?m)^USE_REAL_ROBOT\s*=\s*false\s*$", ex)
    assert re.search(r"(?m)^USE_REAL_SIM_REAL\s*=\s*false\s*$", ex)
    assert "LLM_BACKEND=mock" in ex
    from config import settings

    assert settings.DEFAULT_MODEL_REL.replace("\\", "/") == "builtin_arm2/model.xml"
    assert not bool(getattr(settings, "USE_REAL_ROBOT", False))


def _assert_hard_rules() -> None:
    from core.schemas import TaskSpec
    from plugins.robot.base import BaseRobot

    d = TaskSpec(task_id="t", action="grab", target="cup").to_dict()
    for k in ("task_id", "action", "target", "constraints", "params", "source", "raw_text", "steps"):
        assert k in d
    assert d["steps"] == []
    assert hasattr(BaseRobot, "execute_task")


def _assert_tier_a_features_complete() -> None:
    """档 A：动作表 + steps + 解析 + 顺序执行 + 网站。"""
    from core.action_catalog import ALLOWED_ACTIONS, ACTION_WAIT
    from core.multi_step_contract import MAX_MULTI_STEPS, format_multi_step_message, is_multi_step
    from core.schemas import TaskSpec
    from frontend.capability_panel import feature_catalog_items
    from plugins.llm.mock_llm import MockLLM
    from core.bootstrap import create_robot
    from core.pipeline import Pipeline
    from plugins.engines.mock_engine import MockEngine

    assert ACTION_WAIT in ALLOWED_ACTIONS
    assert {"grab", "place", "move", "home", "wait"} <= set(ALLOWED_ACTIONS)
    assert MAX_MULTI_STEPS == 5

    # 单步兼容
    d0 = TaskSpec(task_id="a", action="home", target="").to_dict()
    assert d0["steps"] == []
    assert not is_multi_step(d0["steps"])

    # 解析 + 执行
    pipe = Pipeline(llm=MockLLM(), engine=MockEngine(), robot=create_robot())
    r = pipe.run_instruction("先回零再抓红色杯子", model_ref="default", real_sim_real=False, save_data=False)
    assert r.ok, r.to_dict()
    assert len(r.data["task_spec"]["steps"]) == 2
    assert (r.data["sim_result"]["metrics"] or {}).get("step_count") == 2

    msg = format_multi_step_message(
        r.data["task_spec"],
        r.data["sim_result"].get("metrics"),
        r.data.get("multi_step"),
    )
    assert "多步" in msg or "2" in msg
    assert "工业" in msg or "教学" in msg

    ids = [x["id"] for x in feature_catalog_items()]
    assert "multi_step" in ids

    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    assert "format_multi_step_message" in app
    assert "demo_sample_" in app
    assert "先回零再抓" in app
    from core.instruction_guard import demo_instruction_samples

    assert any(s.get("id") == "multi_step" for s in demo_instruction_samples())

    plan = (_ROOT / "core" / "阶段14_正式流程_多步与扩动作.txt").read_text(encoding="utf-8")
    assert "档 B" in plan
    assert "params.steps" in plan or "仿真细分" in plan


def _assert_phase15_not_blocked() -> None:
    plan = (_ROOT / "core" / "总规划_不超过15期.md").read_text(encoding="utf-8")
    assert "15" in plan and ("部署" in plan or "可视化" in plan)
    remind = (_ROOT / "core" / "后期完善提醒_11到15.txt").read_text(encoding="utf-8")
    assert "部署" in remind or "Kimi" in remind or "Streamlit" in remind


def main() -> None:
    for mod, token in [
        ("core.smoke_phase14_step1", "SMOKE_PHASE14_STEP1_OK"),
        ("core.smoke_phase14_step2", "SMOKE_PHASE14_STEP2_OK"),
        ("core.smoke_phase14_step3", "SMOKE_PHASE14_STEP3_OK"),
        ("core.smoke_phase14_step4", "SMOKE_PHASE14_STEP4_OK"),
    ]:
        out = _run_module(mod)
        assert token in out, f"{mod} 未打印 {token}"

    _assert_defaults_safe()
    _assert_hard_rules()
    _assert_tier_a_features_complete()
    _assert_phase15_not_blocked()

    for mod, token in [
        ("core.smoke_phase13", "PHASE13_ACCEPTANCE_PASS"),
        ("core.smoke_feature_visible", "SMOKE_FEATURE_VISIBLE_OK"),
        ("core.smoke_phase9_step1", "SMOKE_PHASE9_STEP1_OK"),
        ("core.smoke_step3", "SMOKE_STEP3_OK"),
    ]:
        out = _run_module(mod)
        assert token in out, f"{mod} 未打印 {token}"

    print("PHASE14_ACCEPTANCE_PASS")


if __name__ == "__main__":
    main()
