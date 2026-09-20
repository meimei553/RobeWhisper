# -*- coding: utf-8 -*-
"""
自然语言 → TaskSpec 的大模型抽象基类。

成功/失败契约（阶段 3 冻结）：
- 成功：ApiResult(ok=True, code='OK', data={'task_spec': TaskSpec.to_dict()})
- 失败：ok=False，code 仅使用：
  PARSE_FAILED  空输入或无法解析
  REJECTED      模型拒绝/不安全/无法识别
  TIMEOUT       调用超时
  NETWORK       断网或 HTTP 失败
  INTERNAL      其它内部错误（前端只展示友好 message）
message 必须是用户可读中文，禁止返回原始堆栈。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.schemas import ApiResult

# 稳定错误码（编排层与前端可依赖）
LLM_CODE_OK = "OK"
LLM_CODE_PARSE_FAILED = "PARSE_FAILED"
LLM_CODE_REJECTED = "REJECTED"
LLM_CODE_TIMEOUT = "TIMEOUT"
LLM_CODE_NETWORK = "NETWORK"
LLM_CODE_INTERNAL = "INTERNAL"

FRIENDLY_BLOCKED = "思考遇到一些阻碍，请稍后再试。"


class BaseLLM(ABC):
    """产品主流程只依赖本接口；具体云端 API 在子类中实现。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """适配器名称，便于日志。"""

    @abstractmethod
    def parse_instruction(self, text: str, task_id: str) -> ApiResult:
        """将自然语言解析为 TaskSpec（形态见模块文档）。"""
