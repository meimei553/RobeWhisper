# -*- coding: utf-8 -*-
"""阶段 3 · 步骤 1：LLM 可插拔骨架验收。"""

from __future__ import annotations

import os
import sys
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _reload_settings_bootstrap() -> None:
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)


def main() -> None:
    from core.schemas import TaskSpec
    from plugins.llm.api_llm import ApiLLM
    from plugins.llm.base import BaseLLM
    from plugins.llm.json_extract import parse_model_text_to_task
    from plugins.llm.mock_llm import MockLLM

    # mock 后端
    os.environ["LLM_BACKEND"] = "mock"
    os.environ.pop("LLM_API_KEY", None)
    os.environ.pop("LLM_API_BASE", None)
    os.environ.pop("LLM_MODEL_NAME", None)
    _reload_settings_bootstrap()
    import core.bootstrap as bootstrap

    llm = bootstrap.create_llm()
    assert isinstance(llm, MockLLM)
    assert isinstance(llm, BaseLLM)
    ok = llm.parse_instruction("把红色杯子拿起来", "t1")
    assert ok.ok and ok.data["task_spec"]["action"] == "grab"

    # api 后端但无 Key → 回退 mock，不崩
    os.environ["LLM_BACKEND"] = "api"
    os.environ["LLM_API_BASE"] = ""
    os.environ["LLM_API_KEY"] = ""
    os.environ["LLM_MODEL_NAME"] = ""
    _reload_settings_bootstrap()
    llm2 = bootstrap.create_llm()
    assert isinstance(llm2, MockLLM)

    # ApiLLM 实例在未配置时 parse 返回失败而非抛异常
    bare = ApiLLM(api_base="", api_key="", model_name="")
    assert not bare.is_configured()
    failed = bare.parse_instruction("拿起杯子", "t2")
    assert not failed.ok
    assert failed.code in {"INTERNAL", "PARSE_FAILED", "NETWORK"}

    # JSON 提取骨架
    parsed = parse_model_text_to_task(
        '{"action":"place","target":"table","constraints":{},"params":{}}',
        task_id="t3",
        raw_user="放到桌上",
        source="llm",
    )
    assert parsed.ok and parsed.data["task_spec"]["action"] == "place"

    # 契约未改；pipeline 不直接 import ApiLLM
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
    pipe = (_ROOT / "core/pipeline.py").read_text(encoding="utf-8")
    assert "ApiLLM" not in pipe
    app = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    assert "openai" not in app.lower() or "api_key" not in app.lower()

    print("SMOKE_PHASE3_STEP1_OK")
    print("mock_action", ok.data["task_spec"]["action"], "api_fallback", type(llm2).__name__)


if __name__ == "__main__":
    main()
