# -*- coding: utf-8 -*-
"""阶段 4 总验收：实验导出 + 经验复用。"""

from __future__ import annotations

import os
import sys
import urllib.request
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

    from config import settings
    from core.bootstrap import create_engine, create_llm, create_robot
    from core.experience_store import find_experience, list_experiences
    from core.experiment_store import list_recent_experiments
    from core.pipeline import Pipeline
    from core.schemas import TaskSpec

    engine = create_engine()
    pipe = Pipeline(llm=create_llm(), engine=engine, robot=create_robot())

    r1 = pipe.run_instruction("把桌上的红色杯子拿起来")
    assert r1.ok, r1.to_dict()
    assert (r1.data or {}).get("experiment", {}).get("ok") == "true"
    exp_path = Path((r1.data or {})["experiment"]["path"])
    assert exp_path.exists()
    assert (settings.EXPERIMENTS_DIR / "summary.csv").exists()
    assert find_experience("grab", "red_cup") is not None

    # 第二次应可能命中经验
    r2 = pipe.run_instruction("把红色杯子拿起来")
    assert r2.ok
    assert (r2.data or {}).get("experience_hit") is True

    # 失败也落盘
    bad = pipe.run_instruction("??????")
    assert not bad.ok
    assert (bad.data or {}).get("experiment", {}).get("ok") == "true"

    assert list_recent_experiments(5)
    assert list_experiences(5)

    app = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    assert "经验库" in app or "experience" in app.lower()
    assert "list_recent_experiments" in app
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

    try:
        with urllib.request.urlopen("http://127.0.0.1:8501", timeout=5) as resp:
            assert resp.status == 200
        site = "UP"
    except Exception:
        site = "DOWN"

    print("PHASE4_ACCEPTANCE_PASS")
    print("experience_hit_second", (r2.data or {}).get("experience_hit"), "site", site)


if __name__ == "__main__":
    main()
