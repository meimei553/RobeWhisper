# -*- coding: utf-8 -*-
"""阶段 3 总复验。用法：python -m core.smoke_phase3"""

from __future__ import annotations

import os
import urllib.request
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    os.environ["ENGINE_BACKEND"] = "mujoco"
    os.environ["LLM_BACKEND"] = "mock"
    import config.settings as settings_mod

    reload(settings_mod)
    import core.bootstrap as bootstrap

    reload(bootstrap)

    from config import settings
    from core.bootstrap import create_engine, create_llm, create_robot
    from core.model_catalog import list_model_options
    from core.pipeline import Pipeline
    from core.schemas import TaskSpec

    assert hasattr(settings, "DEFAULT_MODEL_REL")
    assert settings.DEFAULT_MODEL_REL
    opts = list_model_options()
    assert any(o["ref"] == "default" for o in opts)

    app = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    assert "st.chat_input" in app and "chat_history" in app
    assert "import mujoco" not in app

    engine = create_engine()
    pipe = Pipeline(llm=create_llm(), engine=engine, robot=create_robot())
    ok = pipe.run_instruction("把桌上的红色杯子拿起来")
    assert ok.ok and ok.data["task_spec"]["action"] == "grab"
    assert len(ok.data["sim_result"].get("trajectory") or []) >= 2

    bad = pipe.run_instruction("??????")
    assert not bad.ok

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

    with urllib.request.urlopen("http://127.0.0.1:8501", timeout=8) as resp:
        assert resp.status == 200

    print("PHASE3_ACCEPTANCE_PASS")


if __name__ == "__main__":
    main()
