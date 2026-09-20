# -*- coding: utf-8 -*-
"""视觉接口预留（二期）：阶段 0 仅占位，禁止业务主流程依赖本类。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.schemas import ApiResult


class BaseVLM(ABC):
    """图像 → 语言/结构化结果；本期不实现。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """适配器名称。"""

    @abstractmethod
    def analyze(self, image_ref: str, prompt: str = "") -> ApiResult:
        """预留：输入图像引用与提示，输出结构化 data。"""
