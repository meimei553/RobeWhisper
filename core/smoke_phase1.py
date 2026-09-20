# -*- coding: utf-8 -*-
"""阶段 1 总复验。用法：python -m core.smoke_phase1"""

from __future__ import annotations

import os
import urllib.request
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    from core.schemas import SimResult, TaskSpec
    from plugins.engines.mock_engine import MockEngine

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

    app = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    assert "import mujoco" not in app
    assert "st.slider" in app

    os.environ["ENGINE_BACKEND"] = "mujoco"
    import config.settings as settings_mod

    reload(settings_mod)
    import core.bootstrap as bootstrap

    reload(bootstrap)
    eng = bootstrap.create_engine()
    eng.load("default")
    eng.reset()
    before = eng.get_state()["joint_positions"]
    after = eng.step({"joint_targets": [0.6, -0.5], "nsub": 40})["joint_positions"]
    assert sum(abs(float(x) - float(y)) for x, y in zip(before, after)) > 1e-3

    os.environ["ENGINE_BACKEND"] = "mock"
    reload(settings_mod)
    reload(bootstrap)
    assert isinstance(bootstrap.create_engine(), MockEngine)

    with urllib.request.urlopen("http://127.0.0.1:8501", timeout=8) as resp:
        assert resp.status == 200

    print("PHASE1_ACCEPTANCE_PASS")


if __name__ == "__main__":
    main()
