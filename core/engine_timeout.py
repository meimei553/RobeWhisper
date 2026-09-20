# -*- coding: utf-8 -*-
"""
仿真墙钟超时（第 9 期 · 步骤 3）

协作式检查：在 run_task / step 循环里看 time.monotonic，
不依赖 signal（Windows 可用），不改 TaskSpec 主字段。
"""

from __future__ import annotations

import time
from typing import Any

ENGINE_TIMEOUT_CODE = "ENGINE_TIMEOUT"
FRIENDLY_ENGINE_TIMEOUT = "仿真执行超时，请缩短步数或稍后再试。"


def resolve_engine_timeout_sec(params: dict[str, Any] | None = None) -> float:
    """
    解析超时秒数。
    - 默认读 ENGINE_TIMEOUT_SEC（误配 ≤0 时回退 30，避免“永远立即超时”）
    - params.timeout_sec 若 >0，只允许比默认更严（min），防止 LLM 放宽闸
    """
    from config.safe import setting

    raw = setting("ENGINE_TIMEOUT_SEC", 30)
    try:
        base = float(raw if raw is not None else 30)
    except (TypeError, ValueError):
        base = 30.0
    if base <= 0:
        base = 30.0

    override = None
    if params and params.get("timeout_sec") is not None:
        try:
            override = float(params["timeout_sec"])
        except (TypeError, ValueError):
            override = None
    if override is not None and override > 0:
        return min(base, override)
    return base


def make_deadline(timeout_sec: float) -> float:
    return time.monotonic() + float(timeout_sec)


def is_past_deadline(deadline: float | None) -> bool:
    if deadline is None:
        return False
    return time.monotonic() >= float(deadline)


def timeout_sim_result(
    *,
    task_id: str,
    timeout_sec: float,
    started_at: float,
    trajectory: list[dict[str, Any]] | None = None,
    engine_name: str = "",
    engine_version: str = "",
) -> "SimResult":
    from core.schemas import SimResult

    elapsed = max(0.0, time.monotonic() - float(started_at))
    return SimResult(
        task_id=task_id,
        ok=False,
        trajectory=list(trajectory or []),
        metrics={
            "timed_out": True,
            "timeout_sec": float(timeout_sec),
            "elapsed_sec": elapsed,
            "code": ENGINE_TIMEOUT_CODE,
        },
        message=FRIENDLY_ENGINE_TIMEOUT,
        engine_name=engine_name,
        engine_version=engine_version,
    )


def is_timeout_result(sim: Any) -> bool:
    """从 SimResult 或 dict 判断是否为引擎超时失败。"""
    if sim is None:
        return False
    metrics = getattr(sim, "metrics", None)
    if metrics is None and isinstance(sim, dict):
        metrics = sim.get("metrics")
    if isinstance(metrics, dict) and metrics.get("timed_out"):
        return True
    if isinstance(metrics, dict) and metrics.get("code") == ENGINE_TIMEOUT_CODE:
        return True
    code = getattr(sim, "code", None)
    if code == ENGINE_TIMEOUT_CODE:
        return True
    return False
