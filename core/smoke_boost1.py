# -*- coding: utf-8 -*-
"""
补强包一总复验：步骤 1–4 + 档 A + 硬约束 + 13/14/能力可见回归。

用法：python -m core.smoke_boost1
期望：SMOKE_BOOST1_ACCEPTANCE_PASS
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
    assert not bool(getattr(settings, "USE_REAL_SIM_REAL", False))


def _assert_hard_rules() -> None:
    from core.schemas import ApiResult, SimResult, TaskSpec
    from plugins.robot.base import BaseRobot

    d = TaskSpec(task_id="t", action="grab", target="cup").to_dict()
    for k in ("task_id", "action", "target", "constraints", "params", "source", "raw_text", "steps"):
        assert k in d
    assert d["steps"] == []
    assert hasattr(BaseRobot, "execute_task")
    sr = SimResult(task_id="t", ok=True, message="ok", trajectory=[], metrics={"pose_source": "none"})
    assert sr.metrics.get("pose_source") == "none"
    ar = ApiResult(ok=True, code="OK", message="ok")
    assert "ok" in ar.to_dict()


def _assert_tier_a() -> None:
    """档 A：有物体朝坐标；无物体不假接地；人话非相机非抓住；代理摘要可见。"""
    from core.contact_scene_contract import contact_reason_zh
    from core.pose_grounding_contract import (
        POSE_SOURCE_NONE,
        POSE_SOURCE_SCENE,
        build_proxy_summary,
        format_proxy_summary_lines,
        has_forged_object_pose,
        pose_source_label,
    )
    from core.schemas import TaskSpec
    from frontend.capability_panel import capability_markdown, feature_catalog_items
    from plugins.engines.mujoco_engine import MujocoEngine

    assert "相机" in pose_source_label(POSE_SOURCE_SCENE)
    assert "场景没开" in contact_reason_zh("no_scene")
    assert "够不着" in contact_reason_zh("no_contact")
    assert "抓住" not in contact_reason_zh("ok") or "不是" in contact_reason_zh("ok")

    mj = MujocoEngine()
    mj.load("default")
    r0 = mj.run_task(TaskSpec(task_id="b0", action="grab", target="cup"))
    assert r0.metrics.get("pose_source") == POSE_SOURCE_NONE
    assert r0.metrics.get("object_xpos") in (None, "", [], ())
    assert not has_forged_object_pose(r0.metrics, has_scene=False)

    mj.load("builtin_arm2_contact")
    r1 = mj.run_task(TaskSpec(task_id="b1", action="grab", target="block", params={"steps": 6}))
    assert r1.metrics.get("pose_source") in {POSE_SOURCE_SCENE, "uncertain"}
    if r1.metrics.get("pose_source") == POSE_SOURCE_SCENE:
        assert r1.metrics.get("object_xpos") not in (None, "", [], ())

    lines = format_proxy_summary_lines(
        build_proxy_summary(
            metrics={"pose_source": "none", "grasp_proxy": "no_scene"},
        )
    )
    joined = "\n".join(lines)
    assert "位姿来源" in joined and "接触代理" in joined

    ids = [x["id"] for x in feature_catalog_items()]
    assert "contact_trial" in ids
    cap = capability_markdown("mock")
    assert "不是相机" in cap
    assert "已经抓住" not in cap
    assert "标定完成" not in cap
    assert "看见杯子" not in cap

    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    assert "本次试机代理摘要" in app
    assert "不是相机" in app
    assert "看见杯子" not in app
    assert "已经抓住" not in app
    assert "标定完成" not in app


def _assert_phase15_not_done_not_blocked() -> None:
    plan = (_ROOT / "core" / "总规划_不超过15期.md").read_text(encoding="utf-8")
    assert "15" in plan and ("部署" in plan or "可视化" in plan)
    assert "最后" in plan
    app = (_ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
    # 未提前做成公网主路径 / 3D 主视口
    assert "streamlit.io" not in app.lower()
    assert "three.js" not in app.lower()


def main() -> None:
    for mod, token in [
        ("core.smoke_boost1_step1", "SMOKE_BOOST1_STEP1_OK"),
        ("core.smoke_boost1_step2", "SMOKE_BOOST1_STEP2_OK"),
        ("core.smoke_boost1_step3", "SMOKE_BOOST1_STEP3_OK"),
        ("core.smoke_boost1_step4", "SMOKE_BOOST1_STEP4_OK"),
    ]:
        out = _run_module(mod)
        assert token in out, f"{mod} 未打印 {token}"

    _assert_defaults_safe()
    _assert_hard_rules()
    _assert_tier_a()
    _assert_phase15_not_done_not_blocked()

    for mod, token in [
        ("core.smoke_phase14", "PHASE14_ACCEPTANCE_PASS"),
        ("core.smoke_phase13", "PHASE13_ACCEPTANCE_PASS"),
        ("core.smoke_feature_visible", "SMOKE_FEATURE_VISIBLE_OK"),
    ]:
        out = _run_module(mod)
        assert token in out, f"{mod} 未打印 {token}"

    print("SMOKE_BOOST1_ACCEPTANCE_PASS")


if __name__ == "__main__":
    main()
