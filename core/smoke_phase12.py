# -*- coding: utf-8 -*-
"""
第 12 期总复验：步骤 1–4 + 默认安全 + 未堵死第13期 + 相关回归。

用法：python -m core.smoke_phase12
期望：PHASE12_ACCEPTANCE_PASS
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
    # 严模式默认关（注释或显式 false 均可；不得默认 true）
    assert "RSR_REQUIRE_REAL_TRAJECTORY=true" not in [
        ln.strip() for ln in ex.splitlines() if ln.strip() and not ln.strip().startswith("#")
    ]


def _assert_hard_rules() -> None:
    from core.schemas import TaskSpec
    from core.rsr_loop import run_rsr_iteration
    from plugins.robot.base import BaseRobot

    # 契约主字段仍在
    d = TaskSpec(task_id="t", action="grab", target="cup").to_dict()
    for k in ("task_id", "action", "target", "constraints", "params"):
        assert k in d
    assert hasattr(BaseRobot, "execute_task")

    class _E:
        def list_physics_params(self) -> dict:
            return {"friction": 0.5, "joint_damping": 0.1}

        def set_physics_params(self, **kwargs) -> None:
            return None

    sim = [{"t": 0.0, "joint_positions": [0.0, 0.1]}, {"t": 1.0, "joint_positions": [0.1, 0.2]}]
    # 无轨迹 → 伪对照保底
    p = run_rsr_iteration(_E(), sim, {"ok": True, "data": {}})
    assert p.get("reference_source") == "pseudo_real"
    assert p.get("policy") == "prefer_real"
    # 有轨迹 → 必须 robot
    good = {
        "ok": True,
        "data": {"ack": {"trajectory": [{"t": 0.0, "joint_positions": [0.05, 0.15]}, {"t": 1.0, "joint_positions": [0.15, 0.25]}]}},
    }
    r = run_rsr_iteration(_E(), sim, good)
    assert r.get("reference_source") == "robot"
    # 严模式无轨迹 → skip
    s = run_rsr_iteration(_E(), sim, {"ok": True, "data": {}}, require_real_trajectory=True)
    assert s.get("skipped") is True


def _assert_phase13_not_blocked() -> None:
    """未提前实现接触抓取，也不删送单/轨迹口。"""
    # 接触抓取相关不应被误写成已完成硬依赖
    plan = (_ROOT / "core" / "总规划_不超过15期.md").read_text(encoding="utf-8")
    assert "13 接触抓取" in plan or "接触抓取" in plan
    # 假接收端轨迹开关仍在（第12期交付，供第13前后继续用）
    fake = (_ROOT / "plugins" / "robot" / "local_fake_receiver.py").read_text(encoding="utf-8")
    assert "--with-trajectory" in fake


def main() -> None:
    for mod, token in [
        ("core.smoke_phase12_step1", "SMOKE_PHASE12_STEP1_OK"),
        ("core.smoke_phase12_step2", "SMOKE_PHASE12_STEP2_OK"),
        ("core.smoke_phase12_step3", "SMOKE_PHASE12_STEP3_OK"),
        ("core.smoke_phase12_step4", "SMOKE_PHASE12_STEP4_OK"),
    ]:
        out = _run_module(mod)
        assert token in out, f"{mod} 未打印 {token}"

    _assert_defaults_safe()
    _assert_hard_rules()
    _assert_phase13_not_blocked()

    # 回归：第11期桥自检、第6期 RSR、能力可见总验（若过重可只跑关键步）
    for mod, token in [
        ("core.smoke_phase11_step4", "SMOKE_PHASE11_STEP4_OK"),
        ("core.smoke_phase6_step3", "SMOKE_PHASE6_STEP3_OK"),
        ("core.smoke_feature_visible_step4", "SMOKE_FEATURE_VISIBLE_STEP4_OK"),
    ]:
        out = _run_module(mod)
        assert token in out, f"{mod} 未打印 {token}"

    print("PHASE12_ACCEPTANCE_PASS")


if __name__ == "__main__":
    main()
