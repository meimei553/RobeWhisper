# -*- coding: utf-8 -*-
"""
阶段 0 · 步骤 3 烟雾脚本：验证 Mock 全链路。

用法（在项目根目录）：
  python -m core.smoke_step3
"""

from __future__ import annotations

from core.bootstrap import create_pipeline
from plugins.engines.base import BaseEngine
from plugins.llm.base import BaseLLM
from plugins.robot.base import BaseRobot


def main() -> None:
    pipeline = create_pipeline()

    # 勘误点：Pipeline 持有的应是基类实例
    assert isinstance(pipeline._llm, BaseLLM)
    assert isinstance(pipeline._engine, BaseEngine)
    assert isinstance(pipeline._robot, BaseRobot)

    ok = pipeline.run_instruction("把桌上的红色杯子拿起来")
    assert ok.ok, ok.to_dict()
    assert ok.data and "task_spec" in ok.data and "sim_result" in ok.data
    assert ok.data["task_spec"]["action"] == "grab"
    assert ok.data["task_spec"]["target"] == "red_cup"
    assert ok.data["sim_result"]["ok"] is True
    assert len(ok.data["sim_result"]["trajectory"]) >= 2
    assert ok.data["robot_result"]["ok"] is True

    bad = pipeline.run_instruction("??????")
    assert not bad.ok
    assert bad.code in ("REJECTED", "PARSE_FAILED")
    assert "阻碍" in bad.message or "无法识别" in bad.message

    empty = pipeline.run_instruction("   ")
    assert not empty.ok

    print("SMOKE_STEP3_OK")
    print("adapters=", ok.data["adapters"])
    print("action=", ok.data["task_spec"]["action"], "target=", ok.data["task_spec"]["target"])


if __name__ == "__main__":
    main()
