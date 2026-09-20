# -*- coding: utf-8 -*-
"""真机执行抽象基类（含 execute_task 预留）。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.schemas import ApiResult, TaskSpec


class BaseRobot(ABC):
    """真机或模拟真机；阶段 0 使用 Mock，阶段 5 再接真实通讯。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """适配器名称。"""

    @abstractmethod
    def execute_task(self, task: TaskSpec) -> ApiResult:
        """
        执行与仿真侧同一套 TaskSpec。

        成功/失败均返回 ApiResult；禁止把底层通讯堆栈抛给前端。
        """
