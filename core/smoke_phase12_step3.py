# -*- coding: utf-8 -*-
"""第 12 期 · 步骤 3：RSR 策略显式化（真优先 / 伪保底 / 严模式）。"""

from __future__ import annotations

import os
import sys
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _sim(n: int = 3, dim: int = 2) -> list[dict]:
    return [{"t": float(i), "joint_positions": [0.1 * i] * dim} for i in range(n)]


def _eng():
    class _E:
        def list_physics_params(self) -> dict:
            return {"friction": 0.5, "joint_damping": 0.1}

        def set_physics_params(self, **kwargs) -> None:
            return None

    return _E()


def main() -> None:
    from core.rsr_loop import resolve_rsr_policy, run_rsr_iteration

    pol = resolve_rsr_policy(require_real_trajectory=False)
    assert pol["policy"] == "prefer_real" and pol["allow_pseudo_real"] is True
    pol_r = resolve_rsr_policy(require_real_trajectory=True)
    assert pol_r["policy"] == "require_real" and pol_r["allow_pseudo_real"] is False

    sim = _sim()
    empty_rr = {"ok": True, "data": {}}

    # 默认 prefer_real：无轨迹 → 伪对照
    r_pseudo = run_rsr_iteration(_eng(), sim, empty_rr)
    assert r_pseudo.get("reference_source") == "pseudo_real"
    assert r_pseudo.get("policy") == "prefer_real"
    assert int(r_pseudo.get("reference_frame_count") or 0) >= 1
    assert r_pseudo.get("skipped") is False

    # 严模式：无轨迹 → skipped
    r_skip = run_rsr_iteration(
        _eng(), sim, empty_rr, require_real_trajectory=True
    )
    assert r_skip.get("skipped") is True
    assert r_skip.get("ok") is False
    assert r_skip.get("policy") == "require_real"
    assert "伪对照" in str(r_skip.get("message") or "") or "跳过" in str(r_skip.get("message") or "")

    # 有真轨迹：即使严模式也必须 robot（硬门槛）
    good = {
        "ok": True,
        "data": {
            "ack": {
                "trajectory": [
                    {"t": 0.0, "joint_positions": [0.05, 0.05]},
                    {"t": 1.0, "joint_positions": [0.15, 0.15]},
                    {"t": 2.0, "joint_positions": [0.25, 0.25]},
                ]
            }
        },
    }
    r_real = run_rsr_iteration(_eng(), sim, good, require_real_trajectory=True)
    assert r_real.get("reference_source") == "robot"
    assert r_real.get("skipped") is False
    assert r_real.get("policy") == "require_real"
    assert int(r_real.get("reference_frame_count") or 0) == 3

    # 有真轨迹 + prefer_real：也必须 robot，禁止静默伪对照
    r_hard = run_rsr_iteration(_eng(), sim, good, require_real_trajectory=False)
    assert r_hard.get("reference_source") == "robot"
    assert r_hard.get("policy") == "prefer_real"

    # Pipeline 读配置：默认不严 → 无真发时伪对照
    os.environ["ENGINE_BACKEND"] = "mujoco"
    os.environ["LLM_BACKEND"] = "mock"
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    os.environ["USE_REAL_SIM_REAL"] = "false"
    os.environ["RSR_REQUIRE_REAL_TRAJECTORY"] = "false"
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)
    assert bool(settings_mod.RSR_REQUIRE_REAL_TRAJECTORY) is False

    from core.bootstrap import create_engine, create_llm, create_robot
    from core.pipeline import Pipeline

    pipe = Pipeline(llm=create_llm(), engine=create_engine(), robot=create_robot())
    out = pipe.run_instruction("抓起红色积木", real_sim_real=True)
    assert out.ok, out.to_dict()
    rsr = (out.data or {}).get("rsr") or {}
    assert rsr.get("reference_source") == "pseudo_real"
    assert rsr.get("policy") == "prefer_real"
    assert "reference_frame_count" in rsr

    # 严模式配置：无真轨迹 → skipped
    os.environ["RSR_REQUIRE_REAL_TRAJECTORY"] = "true"
    reload(settings_mod)
    reload(bootstrap)
    pipe2 = Pipeline(llm=create_llm(), engine=create_engine(), robot=create_robot())
    out2 = pipe2.run_instruction("回零", real_sim_real=True)
    assert out2.ok, out2.to_dict()
    rsr2 = (out2.data or {}).get("rsr") or {}
    assert rsr2.get("skipped") is True
    assert rsr2.get("policy") == "require_real"

    # 恢复默认，避免污染后续
    os.environ["RSR_REQUIRE_REAL_TRAJECTORY"] = "false"
    reload(settings_mod)
    reload(bootstrap)

    ex = (_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "RSR_REQUIRE_REAL_TRAJECTORY" in ex

    print("SMOKE_PHASE12_STEP3_OK")


if __name__ == "__main__":
    main()
