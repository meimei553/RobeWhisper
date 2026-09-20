# -*- coding: utf-8 -*-
"""
多步顺序执行辅助（第 14 期 · 步骤 3）

Pipeline 按 TaskSpec.steps 逐段调用引擎 run_task；
单步 TaskSpec（steps 空）不走本模块。
"""

from __future__ import annotations

from typing import Any

from core.multi_step_contract import is_multi_step
from core.schemas import SimResult, TaskSpec


def iter_step_specs(parent: TaskSpec) -> list[TaskSpec]:
    """把多步父任务展开为若干叶子 TaskSpec（steps 清空）。"""
    if not is_multi_step(parent.steps):
        return []
    out: list[TaskSpec] = []
    for i, st in enumerate(parent.steps):
        params = dict(st.get("params") or {})
        # 继承父级 model_ref，便于同一模型连续执行
        if "model_ref" not in params and parent.params.get("model_ref"):
            params["model_ref"] = parent.params["model_ref"]
        out.append(
            TaskSpec(
                task_id=f"{parent.task_id}_s{i + 1}",
                action=str(st.get("action") or ""),
                target=str(st.get("target") or ""),
                constraints=dict(st.get("constraints") or {}),
                params=params,
                source=parent.source,
                raw_text=parent.raw_text,
                steps=[],
            )
        )
    return out


def merge_step_sim_results(
    *,
    parent_task_id: str,
    step_results: list[SimResult],
    engine_name: str = "",
    engine_version: str = "",
) -> SimResult:
    """合并多段仿真结果；任一步失败不应调用本函数。"""
    trajectory: list[dict[str, Any]] = []
    actions: list[str] = []
    for i, sr in enumerate(step_results):
        actions.append(str(getattr(sr, "action", "") or ""))
        # 从 message 里不好取 action；用 metrics 旁路
        for frame in list(sr.trajectory or []):
            fr = dict(frame)
            fr["multi_step_index"] = i + 1
            trajectory.append(fr)

    last_metrics: dict[str, Any] = {}
    if step_results:
        last_metrics = dict(step_results[-1].metrics or {})

    metrics: dict[str, Any] = dict(last_metrics)
    metrics["multi_step"] = True
    metrics["step_count"] = len(step_results)
    metrics["step_actions"] = [
        # 从各段 message 不可靠；由调用方可再填。此处用 trajectory 标记数
    ]
    # 尽量从各段 metrics 旁路留下的信息不强依赖；由 pipeline 写入 step_actions
    labels = []
    for sr in step_results:
        # SimResult 无 action 字段；pipeline 传入前可写进 metrics
        lab = (sr.metrics or {}).get("step_action")
        if lab:
            labels.append(str(lab))
    if labels:
        metrics["step_actions"] = labels

    msg = f"已按序执行 {len(step_results)} 步"
    if labels:
        msg = msg + "：" + " → ".join(labels)

    return SimResult(
        task_id=parent_task_id,
        ok=True,
        trajectory=trajectory,
        metrics=metrics,
        message=msg,
        engine_name=engine_name or (step_results[-1].engine_name if step_results else ""),
        engine_version=engine_version
        or (step_results[-1].engine_version if step_results else "0"),
    )


def annotate_step_metrics(sim: SimResult, *, action: str, step_index: int, step_total: int) -> SimResult:
    """给单段结果打上多步旁路标记（不改主字段名）。"""
    m = dict(sim.metrics or {})
    m["step_action"] = action
    m["step_index"] = step_index
    m["step_total"] = step_total
    return SimResult(
        task_id=sim.task_id,
        ok=sim.ok,
        trajectory=list(sim.trajectory or []),
        metrics=m,
        message=sim.message,
        engine_name=sim.engine_name,
        engine_version=sim.engine_version,
    )
