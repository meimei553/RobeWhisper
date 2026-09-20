# -*- coding: utf-8 -*-
"""Mock 仿真引擎：不依赖真实物理库，仅用于打通契约链路。"""

from __future__ import annotations

import time
from typing import Any

from core.engine_timeout import (
    is_past_deadline,
    make_deadline,
    resolve_engine_timeout_sec,
    timeout_sim_result,
)
from core.schemas import SimResult, TaskSpec
from plugins.engines.base import BaseEngine


class MockEngine(BaseEngine):
    """内存假仿真：用关节角列表模拟步进。"""

    def __init__(self) -> None:
        self._model_ref: str = ""
        self._loaded: bool = False
        # 假想 6 轴关节角（弧度占位，仅演示）
        self._joints: list[float] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self._t: int = 0
        self._run_deadline: float | None = None
        # 阶段 2：Mock 物理参数白名单（假值，仅保证接口可用）
        self._physics: dict[str, Any] = {
            "friction": 1.0,
            "joint_damping": 0.5,
            "joint_range_min": -2.8,
            "joint_range_max": 2.8,
        }

    @property
    def name(self) -> str:
        return "mock_engine"

    @property
    def version(self) -> str:
        return "0.1.0"

    def load(self, model_ref: str) -> None:
        self._model_ref = model_ref or "builtin_mock_arm"
        self._loaded = True
        self.reset()

    def reset(self) -> None:
        if not self._loaded:
            # 未 load 时也允许 reset 到默认，便于烟雾测试
            self._loaded = True
            self._model_ref = self._model_ref or "builtin_mock_arm"
        self._joints = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self._t = 0

    def step(self, control: dict[str, Any] | TaskSpec) -> dict[str, Any]:
        if isinstance(control, TaskSpec):
            delta = float(control.params.get("joint_delta", 0.1))
            action = control.action
        else:
            delta = float(control.get("joint_delta", 0.1))
            action = str(control.get("action", "move"))

        # 简单假动力学：按动作轻微改变关节角
        if action == "wait":
            # 等待：不改关节，仅推进时间戳
            pass
        elif action in ("grab", "place", "move", "home"):
            self._joints = [j + delta for j in self._joints]
            if action == "home":
                self._joints = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self._t += 1
        return self.get_state()

    def get_state(self) -> dict[str, Any]:
        return {
            "t": self._t,
            "model_ref": self._model_ref,
            "joint_positions": list(self._joints),
        }

    def run_task(self, task: TaskSpec) -> SimResult:
        if not self._loaded:
            self.load("builtin_mock_arm")
        timeout_sec = resolve_engine_timeout_sec(task.params)
        started_at = time.monotonic()
        self._run_deadline = make_deadline(timeout_sec)
        trajectory: list[dict[str, Any]] = [self.get_state()]
        try:
            # 假执行若干步，形成轨迹
            steps = int(task.params.get("steps", 3))
            if str(task.action or "") == "wait":
                steps = int(task.params.get("steps", 1) or 1)
            for _ in range(max(1, steps)):
                if is_past_deadline(self._run_deadline):
                    return timeout_sim_result(
                        task_id=task.task_id,
                        timeout_sec=timeout_sec,
                        started_at=started_at,
                        trajectory=trajectory,
                        engine_name=self.name,
                        engine_version=self.version,
                    )
                trajectory.append(self.step(task))
            from core.contact_probe import build_contact_metrics
            from core.contact_scene_contract import is_contact_scene_model_ref

            # Mock：按 model_ref + 可选 params 注入可预测接触结果（无 MuJoCo 也能测文案）
            has_scene = is_contact_scene_model_ref(self._model_ref) or bool(
                (task.params or {}).get("mock_contact_scene")
            )
            if has_scene:
                forced = str((task.params or {}).get("mock_grasp_proxy") or "").strip()
                if forced == "ok":
                    contact_m = build_contact_metrics(
                        has_scene=True,
                        action=str(task.action or ""),
                        contact_detected=True,
                        object_moved=True,
                        ee_object_distance=0.04,
                    )
                elif forced == "no_contact":
                    contact_m = build_contact_metrics(
                        has_scene=True,
                        action=str(task.action or ""),
                        contact_detected=False,
                        object_moved=False,
                        ee_object_distance=0.45,
                    )
                else:
                    # 默认：grab 视为不确定接近，其它 no_contact
                    act = str(task.action or "")
                    contact_m = build_contact_metrics(
                        has_scene=True,
                        action=act,
                        contact_detected=False,
                        object_moved=False,
                        ee_object_distance=0.12 if act in {"grab", "place"} else 0.40,
                    )
            else:
                contact_m = build_contact_metrics(has_scene=False, action=str(task.action or ""))

            from core.planar_aim import apply_scene_aim_to_task

            mock_xpos = (task.params or {}).get("mock_object_xpos")
            if has_scene and mock_xpos is None:
                mock_xpos = [0.36, 0.18, 0.04]
            if not has_scene:
                mock_xpos = mock_xpos  # sanitize 会清掉
            xpos_list = None
            if isinstance(mock_xpos, (list, tuple)) and len(mock_xpos) >= 2:
                xpos_list = [float(x) for x in mock_xpos[:3]]
            _task2, pose_m = apply_scene_aim_to_task(
                task, has_scene=has_scene, object_xpos=xpos_list
            )
            # Mock 步进已结束；位姿只写入 metrics（示意目标不改假关节亦可）

            metrics = {
                "steps": len(trajectory) - 1,
                "stable": 1.0,
                "elapsed_sec": max(0.0, time.monotonic() - started_at),
                "timeout_sec": timeout_sec,
            }
            metrics.update(contact_m)
            metrics.update(pose_m)
            return SimResult(
                task_id=task.task_id,
                ok=True,
                trajectory=trajectory,
                metrics=metrics,
                message=f"Mock 引擎已执行 action={task.action} target={task.target}",
                engine_name=self.name,
                engine_version=self.version,
            )
        finally:
            self._run_deadline = None

    def list_physics_params(self) -> dict[str, Any]:
        return dict(self._physics)

    def get_joint_limits(self) -> list[tuple[float, float]]:
        """Mock：六轴使用同一宽限位，供安全闸联调。"""
        lo = float(self._physics.get("joint_range_min", -2.8))
        hi = float(self._physics.get("joint_range_max", 2.8))
        return [(lo, hi) for _ in range(len(self._joints))]

    def set_physics_params(self, params: dict[str, Any]) -> dict[str, Any]:
        skipped: list[str] = []
        for key, value in (params or {}).items():
            if key in self._physics:
                self._physics[key] = float(value)
            else:
                skipped.append(str(key))
        out = dict(self._physics)
        out["skipped"] = skipped
        return out
