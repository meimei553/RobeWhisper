# -*- coding: utf-8 -*-
"""阶段4·步骤3：Pipeline 落盘 + 经验复用。"""

from __future__ import annotations

import os
import sys
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    os.environ["ENGINE_BACKEND"] = "mujoco"
    os.environ["LLM_BACKEND"] = "mock"
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)

    from core.bootstrap import create_engine, create_llm, create_robot
    from core.experience_store import find_experience
    from core.pipeline import Pipeline

    pipe = Pipeline(llm=create_llm(), engine=create_engine(), robot=create_robot())
    r1 = pipe.run_instruction("把桌上的红色杯子拿起来")
    assert r1.ok and (r1.data or {}).get("experiment", {}).get("ok") == "true"
    assert find_experience("grab", "red_cup") is not None

    r2 = pipe.run_instruction("把红色杯子拿起来")
    assert r2.ok and (r2.data or {}).get("experience_hit") is True

    pipe_src = (_ROOT / "core/pipeline.py").read_text(encoding="utf-8")
    assert "MujocoEngine" not in pipe_src and "remember_experience" in pipe_src
    print("SMOKE_PHASE4_STEP3_OK", "hit", (r2.data or {}).get("experience_hit"))


if __name__ == "__main__":
    main()
