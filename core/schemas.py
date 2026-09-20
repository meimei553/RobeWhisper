# -*- coding: utf-8 -*-
"""
RobeWhisper 核心数据契约（阶段 0 · 步骤 2）

全链路只认这些结构：
- TaskSpec：意图（LLM/UI → 引擎/真机）
- SimResult：仿真会话产出
- ApiResult：统一成败包装（前端只读 ok/code/message）

禁止在字段名中写入具体仿真引擎、真机中间件或某家模型厂商的专用前缀。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TaskSpec:
    """结构化任务意图：自然语言解析后的唯一「货币」。"""

    # 任务唯一编号（由编排层生成，便于日志与回流对齐）
    task_id: str
    # 动作名，如 move / grab / place / home / wait（字符串枚举，见 action_catalog）
    action: str
    # 作用对象，如 red_cup；无可为 ""
    target: str = ""
    # 约束（关节限位、速度上限等业务约束，不绑具体引擎）
    constraints: dict[str, Any] = field(default_factory=dict)
    # 附加参数（目标位姿、夹爪开合等，键名保持通用）
    # 注意：params["steps"] 是单次仿真细分步数，不是多步编排
    params: dict[str, Any] = field(default_factory=dict)
    # 来源：llm | ui | experience | mock
    source: str = "mock"
    # 用户原始自然语言（可选，便于追溯）
    raw_text: str = ""
    # 可选多步编排：[{action, target, constraints?, params?}, ...]；空列表=旧单步语义
    steps: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """序列化为普通字典，便于 JSON 导出。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskSpec":
        """从字典安全构造（只取已知字段，忽略多余键）。"""
        from core.multi_step_contract import normalize_steps

        raw_steps = data.get("steps")
        steps = normalize_steps(raw_steps) if raw_steps is not None else []
        return cls(
            task_id=str(data.get("task_id", "")),
            action=str(data.get("action", "")),
            target=str(data.get("target", "")),
            constraints=dict(data.get("constraints") or {}),
            params=dict(data.get("params") or {}),
            source=str(data.get("source", "mock")),
            raw_text=str(data.get("raw_text", "")),
            steps=steps,
        )


@dataclass
class SimResult:
    """一次仿真执行（或若干 step 汇总）的结果。"""

    task_id: str
    ok: bool
    # 轨迹：每帧为通用状态快照（如 joint_positions / timestamp），不绑引擎类型
    trajectory: list[dict[str, Any]] = field(default_factory=list)
    # 指标：成功率、稳定性占位等
    metrics: dict[str, Any] = field(default_factory=dict)
    # 给用户看的说明（成功或失败原因摘要）
    message: str = ""
    # 适配器标识（便于日后换引擎对照），非引擎内部句柄
    engine_name: str = "mock"
    engine_version: str = "0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SimResult":
        return cls(
            task_id=str(data.get("task_id", "")),
            ok=bool(data.get("ok", False)),
            trajectory=list(data.get("trajectory") or []),
            metrics=dict(data.get("metrics") or {}),
            message=str(data.get("message", "")),
            engine_name=str(data.get("engine_name", "mock")),
            engine_version=str(data.get("engine_version", "0")),
        )


@dataclass
class ApiResult:
    """
    统一对外结果包装。

    前端规则：ok=False 时只展示友好 message，不抛原始堆栈。
    code 建议使用稳定字符串，如 OK / PARSE_FAILED / ENGINE_TIMEOUT / REJECTED。
    """

    ok: bool
    code: str
    message: str
    # 成功时可放 TaskSpec / SimResult 的 dict，或其他业务数据
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def success(cls, message: str = "ok", data: dict[str, Any] | None = None) -> "ApiResult":
        return cls(ok=True, code="OK", message=message, data=data)

    @classmethod
    def fail(cls, code: str, message: str, data: dict[str, Any] | None = None) -> "ApiResult":
        return cls(ok=False, code=code, message=message, data=data)
