# -*- coding: utf-8 -*-
"""
组合根：根据配置组装默认适配器。

只有这里允许 import 具体 Mock 类；业务编排请用 Pipeline + 基类。
"""

from __future__ import annotations

from config.safe import fresh_settings, setting
from core.pipeline import Pipeline
from plugins.engines.base import BaseEngine
from plugins.engines.mock_engine import MockEngine
from plugins.llm.base import BaseLLM
from plugins.llm.mock_llm import MockLLM
from plugins.robot.base import BaseRobot
from plugins.robot.mock_robot import MockRobot


def create_llm() -> BaseLLM:
    """
    组装 LLM 适配器。

    - mock：关键词 Mock
    - api：OpenAI 兼容云端；若缺少 Key/地址/模型名则自动回退 mock，避免崩站
    """
    fresh_settings()
    backend = str(setting("LLM_BACKEND", "mock") or "mock").lower()
    if backend in ("api", "cloud", "openai"):
        from config import settings

        if settings.llm_api_configured():
            from plugins.llm.api_llm import ApiLLM

            return ApiLLM()
        return MockLLM()
    if backend == "mock":
        return MockLLM()
    return MockLLM()


def create_engine() -> BaseEngine:
    fresh_settings()
    backend = str(setting("ENGINE_BACKEND", "mock") or "mock").lower()
    if backend in ("mock",):
        return MockEngine()
    if backend in ("mujoco", "local"):
        from plugins.engines.mujoco_engine import MujocoEngine

        return MujocoEngine()
    return MockEngine()


def create_robot() -> BaseRobot:
    """
    组装真机适配器。

    - mock：本地假执行（默认）
    - http/ros：仅当 USE_REAL_ROBOT=true 且配置齐全时启用；否则回退 mock
    未知值一律回退 mock，保证网站不崩。
    """
    fresh_settings()
    from config import settings

    backend = str(setting("ROBOT_BACKEND", "mock") or "mock").lower()
    if backend == "mock":
        return MockRobot()

    if not bool(setting("USE_REAL_ROBOT", False)):
        return MockRobot()

    if backend == "http":
        if not settings.robot_http_configured():
            return MockRobot()
        try:
            from plugins.robot.http_robot import HttpRobot

            return HttpRobot()
        except Exception:
            return MockRobot()

    if backend in ("ros", "ros2"):
        if not settings.robot_ros_configured():
            return MockRobot()
        try:
            from plugins.robot.ros_robot import RosRobot, ros_runtime_available

            if not ros_runtime_available():
                return MockRobot()
            return RosRobot()
        except Exception:
            return MockRobot()

    return MockRobot()


def create_pipeline(engine: BaseEngine | None = None) -> Pipeline:
    """组装流水线；可注入已有 engine，便于与网站会话共用同一仿真。"""
    return Pipeline(
        llm=create_llm(),
        engine=engine if engine is not None else create_engine(),
        robot=create_robot(),
    )
