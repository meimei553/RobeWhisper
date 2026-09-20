# -*- coding: utf-8 -*-
"""阶段 7 · 步骤 2：网站引导与结果可读性验收。"""

from __future__ import annotations

import os
import sys
from importlib import reload
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    app = (_ROOT / "frontend/app.py").read_text(encoding="utf-8")
    assert "已具备能力一览" in app
    assert "format_success_reply" in app
    assert "format_fail_reply" in app
    assert "详细数据（可选）" in app
    assert "真机与校准默认都关闭" in app
    assert (_ROOT / "frontend/reply_text.py").exists()
    # 不得在页面入口强制打开真机/RSR
    assert "rsr_enable_ui = True" not in app

    os.environ["ENGINE_BACKEND"] = "mujoco"
    os.environ["LLM_BACKEND"] = "mock"
    os.environ["ROBOT_BACKEND"] = "mock"
    os.environ["USE_REAL_ROBOT"] = "false"
    os.environ["USE_REAL_SIM_REAL"] = "false"
    import config.settings as settings_mod
    import core.bootstrap as bootstrap

    reload(settings_mod)
    reload(bootstrap)

    pipe = bootstrap.create_pipeline()
    off = pipe.run_instruction("回零")
    assert off.ok and "rsr" not in (off.data or {})
    assert bool(settings_mod.USE_REAL_ROBOT) is False
    assert bool(settings_mod.USE_REAL_SIM_REAL) is False

    from frontend.reply_text import format_fail_reply, format_success_reply

    text = format_success_reply(
        "指令已在虚拟引擎中执行",
        action="grab",
        target="red_cup",
        frame_count=3,
        experience_hit=False,
        experiment_id="abc",
        robot_name="mock_robot",
        robot_msg="ok",
        rsr_msg="未执行（开关关闭）",
    )
    assert "动作：" in text and "grab" in text
    assert "action=" not in text
    fail = format_fail_reply("解析失败", "PARSE_FAILED")
    assert "PARSE_FAILED" in fail

    print("SMOKE_PHASE7_STEP2_OK")


if __name__ == "__main__":
    main()
