# -*- coding: utf-8 -*-
"""
第 13 期总复验：步骤 1–4 + 档 A 功能清单 + 硬约束 + 相关回归。

用法：python -m core.smoke_phase13
期望：PHASE13_ACCEPTANCE_PASS
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
    assert "RSR_REQUIRE_REAL_TRAJECTORY=true" not in [
        ln.strip() for ln in ex.splitlines() if ln.strip() and not ln.strip().startswith("#")
    ]
    from config import settings

    # 默认仍是无物体臂，不强迫接触场景
    assert settings.DEFAULT_MODEL_REL.replace("\\", "/") == "builtin_arm2/model.xml"
    assert not bool(getattr(settings, "USE_REAL_ROBOT", False))


def _assert_hard_rules() -> None:
    """主契约未改；送单口仍在；接触只进 metrics。"""
    from core.schemas import TaskSpec, SimResult
    from plugins.robot.base import BaseRobot

    d = TaskSpec(task_id="t", action="grab", target="cup").to_dict()
    for k in ("task_id", "action", "target", "constraints", "params"):
        assert k in d
    assert hasattr(BaseRobot, "execute_task")

    # SimResult 仍可用；metrics 为旁路扩展点
    sr = SimResult(
        task_id="t",
        ok=True,
        message="ok",
        trajectory=[],
        metrics={"grasp_proxy": "no_scene"},
    )
    assert sr.metrics.get("grasp_proxy") == "no_scene"


def _assert_tier_a_features_complete() -> None:
    """档 A 必做功能是否齐全（相对正式方案第五节）。"""
    from config import settings
    from core.contact_scene_contract import (
        CONTACT_SCENE_MODEL_REL,
        GRASP_PROXY_VALUES,
        is_contact_scene_model_ref,
        format_contact_trial_message,
        grasp_proxy_label,
    )
    from core.contact_probe import decide_grasp_proxy, build_contact_metrics
    from frontend.capability_panel import feature_catalog_items, contact_scene_status_hint

    # A1 接触场景 MJCF
    assert (settings.MODELS_DIR / CONTACT_SCENE_MODEL_REL).is_file()
    assert is_contact_scene_model_ref("builtin_arm2_contact")
    assert not is_contact_scene_model_ref("builtin_arm2")

    # A2 旁路指标键与枚举
    m = build_contact_metrics(has_scene=True, action="grab", contact_detected=True)
    for k in ("contact_scene", "contact_detected", "grasp_proxy", "object_moved"):
        assert k in m
    assert set(GRASP_PROXY_VALUES) >= {"ok", "no_contact", "no_scene", "uncertain"}
    assert decide_grasp_proxy(
        has_scene=False, action="grab", contact_detected=False, object_moved=False, ee_object_distance=None
    ) == "no_scene"

    # A3 人话诊断（非工业抓住）
    ok_label = grasp_proxy_label("ok")
    assert "工业" in ok_label or "夹稳" in ok_label or "现实" in ok_label
    msg = format_contact_trial_message({"grasp_proxy": "ok", "contact_scene": True})
    assert msg
    assert "工业" in msg or "夹稳" in msg or "现实" in msg

    # A4 能力区入口
    ids = [x["id"] for x in feature_catalog_items()]
    assert "contact_trial" in ids
    hint_on = contact_scene_status_hint("builtin_arm2_contact")
    hint_off = contact_scene_status_hint("default")
    assert hint_on["level"] != hint_off["level"] or hint_on["label"] != hint_off["label"]

    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    assert "切换到接触试机场景并抓一次" in app
    assert "恢复默认臂" in app

    # A5 档 B 未误标为已交付（文案禁上岗）
    plan = (_ROOT / "core" / "阶段13_正式流程_接触抓取试机.txt").read_text(encoding="utf-8")
    assert "档 B（本期不做" in plan or "档 B" in plan
    assert "不上岗" in plan or "不说毕业上岗" in (_ROOT / "core" / "总规划_不超过15期.md").read_text(
        encoding="utf-8"
    )


def _assert_phase14_15_not_blocked() -> None:
    """未提前锁死部署；第15 仍在总规划。多步已由第14期交付。"""
    from core.schemas import TaskSpec

    plan = (_ROOT / "core" / "总规划_不超过15期.md").read_text(encoding="utf-8")
    assert "15" in plan and ("部署" in plan or "可视化" in plan)
    # TaskSpec 可选 steps；空列表=单步兼容
    d = TaskSpec(task_id="t", action="home", target="").to_dict()
    assert "steps" in d
    assert d.get("steps") == []


def main() -> None:
    for mod, token in [
        ("core.smoke_phase13_step1", "SMOKE_PHASE13_STEP1_OK"),
        ("core.smoke_phase13_step2", "SMOKE_PHASE13_STEP2_OK"),
        ("core.smoke_phase13_step3", "SMOKE_PHASE13_STEP3_OK"),
        ("core.smoke_phase13_step4", "SMOKE_PHASE13_STEP4_OK"),
    ]:
        out = _run_module(mod)
        assert token in out, f"{mod} 未打印 {token}"

    _assert_defaults_safe()
    _assert_hard_rules()
    _assert_tier_a_features_complete()
    _assert_phase14_15_not_blocked()

    # 回归：第12期总验、能力可见、安全闸关键步
    for mod, token in [
        ("core.smoke_phase12", "PHASE12_ACCEPTANCE_PASS"),
        ("core.smoke_feature_visible", "SMOKE_FEATURE_VISIBLE_OK"),
        ("core.smoke_phase9_step1", "SMOKE_PHASE9_STEP1_OK"),
    ]:
        out = _run_module(mod)
        assert token in out, f"{mod} 未打印 {token}"

    print("PHASE13_ACCEPTANCE_PASS")


if __name__ == "__main__":
    main()
