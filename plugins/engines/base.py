# -*- coding: utf-8 -*-
"""
仿真引擎抽象基类。

会话约定：load → reset → step* → get_state
高层便捷方法 run_task(TaskSpec) → SimResult，供编排层一次跑完一条意图。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.schemas import SimResult, TaskSpec


class BaseEngine(ABC):
    """产品主流程只依赖本接口，不依赖具体物理引擎实现。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """适配器名称，写入 SimResult.engine_name。"""

    @property
    @abstractmethod
    def version(self) -> str:
        """适配器版本字符串。"""

    @abstractmethod
    def load(self, model_ref: str) -> None:
        """加载模型引用（路径或内置名）；不向契约泄漏引擎私有句柄。"""

    @abstractmethod
    def reset(self) -> None:
        """重置仿真世界到初始状态。"""

    @abstractmethod
    def step(self, control: dict[str, Any] | TaskSpec) -> dict[str, Any]:
        """推进一步，返回通用状态快照。"""

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        """读取当前通用状态快照。"""

    @abstractmethod
    def run_task(self, task: TaskSpec) -> SimResult:
        """按 TaskSpec 执行一段仿真并汇总为 SimResult。"""

    @abstractmethod
    def list_physics_params(self) -> dict[str, Any]:
        """
        列出当前可调物理参数（白名单视图）。

        返回通用字典，例如 friction / joint_damping / joint_range_min 等，
        不暴露引擎私有句柄。
        """

    @abstractmethod
    def set_physics_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        按白名单写入物理参数，返回写入后的参数快照。

        未知键应忽略（或记录在返回的 skipped 中），禁止因此导致进程崩溃。
        """
