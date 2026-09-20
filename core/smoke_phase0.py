# -*- coding: utf-8 -*-
"""
阶段 0 总复验脚本（步骤 5）。

用法（项目根目录）：
  python -m core.smoke_phase0
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

from core.bootstrap import create_pipeline
from core.schemas import ApiResult, SimResult, TaskSpec
from plugins.engines.base import BaseEngine
from plugins.llm.base import BaseLLM
from plugins.robot.base import BaseRobot

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    checks: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            raise AssertionError(msg)
        checks.append(msg)

    need_dirs = [
        "core",
        "plugins/engines",
        "plugins/llm",
        "plugins/vlm",
        "plugins/robot",
        "frontend",
        "models",
        "experiments",
        "experience",
        "config",
    ]
    check(all((ROOT / d).exists() for d in need_dirs), "目录分区齐全")

    check(
        set(TaskSpec(task_id="a", action="m").to_dict())
        == {"task_id", "action", "target", "constraints", "params", "source", "raw_text", "steps"},
        "TaskSpec 主字段冻结",
    )
    check(
        set(SimResult(task_id="a", ok=True).to_dict())
        == {"task_id", "ok", "trajectory", "metrics", "message", "engine_name", "engine_version"},
        "SimResult 主字段冻结",
    )
    check(
        set(ApiResult.success().to_dict()) == {"ok", "code", "message", "data"},
        "ApiResult 主字段冻结",
    )

    pipe_src = (ROOT / "core/pipeline.py").read_text(encoding="utf-8")
    check("MockEngine" not in pipe_src and "MockLLM" not in pipe_src, "pipeline 不绑定 Mock 类名")

    req = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    # 阶段0 当时禁止把重依赖写进契约层；仓库已进入阶段1+，requirements 可含仿真/LLM 客户端。
    # 此处改为：requirements 存在且不含密钥形态；厂商重依赖不得渗入 schemas。
    check(bool(req.strip()), "requirements.txt 存在")
    check("sk-" not in req, "requirements 无密钥占位误写")

    schema = (ROOT / "core/schemas.py").read_text(encoding="utf-8").lower()
    check(all(w not in schema for w in ["mujoco", "pybullet", "ros_", "openai"]), "schemas 无厂商专用名")

    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    check("ENGINE_BACKEND" in env and "sk-" not in env, "配置占位且无真实密钥")

    pipeline = create_pipeline()
    check(isinstance(pipeline._llm, BaseLLM), "llm 为 BaseLLM")
    check(isinstance(pipeline._engine, BaseEngine), "engine 为 BaseEngine")
    check(isinstance(pipeline._robot, BaseRobot), "robot 为 BaseRobot")

    result = pipeline.run_instruction("把红色杯子拿起来")
    check(bool(result.ok), "Mock 全链路成功")
    check(result.data is not None and result.data["task_spec"]["action"] == "grab", "解析 action=grab")

    try:
        with urllib.request.urlopen("http://127.0.0.1:8501", timeout=5) as resp:
            check(resp.status == 200, "临时站 HTTP 200")
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"临时站不可访问: {exc}") from exc

    print("PHASE0_ACCEPTANCE_PASS")
    for item in checks:
        print("[x]", item)


if __name__ == "__main__":
    main()
