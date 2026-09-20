# -*- coding: utf-8 -*-
"""阶段 3 · 步骤 4：网站聊天区验收。"""

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

    from core.bootstrap import create_engine, create_llm, create_robot
    from core.pipeline import Pipeline
    from core.schemas import TaskSpec

    app = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    assert "st.chat_input" in app
    assert "chat_history" in app
    assert "import mujoco" not in app
    assert "ApiLLM" not in app  # 页面不直连云端类

    # 与网站相同：共用 engine 的 Pipeline
    engine = create_engine()
    engine.load("default")
    pipe = Pipeline(llm=create_llm(), engine=engine, robot=create_robot())
    ok = pipe.run_instruction("把红色杯子拿起来", model_ref="default")
    assert ok.ok and ok.data["task_spec"]["action"] == "grab"

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

    print("SMOKE_PHASE3_STEP4_OK")


if __name__ == "__main__":
    main()
