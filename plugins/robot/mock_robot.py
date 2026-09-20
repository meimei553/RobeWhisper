# -*- coding: utf-8 -*-
"""Mock 真机：只记录收到的 TaskSpec，不连接真实硬件。"""

from __future__ import annotations

from core.schemas import ApiResult, TaskSpec
from plugins.robot.base import BaseRobot

FRIENDLY_BLOCKED = "思考遇到一些阻碍，请稍后再试。"


class MockRobot(BaseRobot):
    """预留 execute_task 的假实现。"""

    def __init__(self) -> None:
        self.last_task: TaskSpec | None = None

    @property
    def name(self) -> str:
        return "mock_robot"

    def execute_task(self, task: TaskSpec) -> ApiResult:
        if not task.action:
            return ApiResult.fail("REJECTED", FRIENDLY_BLOCKED)
        self.last_task = task
        return ApiResult.success(
            f"Mock 真机已接收任务 action={task.action}",
            data={"accepted": True, "task_id": task.task_id, "robot": self.name},
        )
