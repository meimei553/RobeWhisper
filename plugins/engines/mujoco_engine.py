# -*- coding: utf-8 -*-
"""
MuJoCo 仿真引擎适配器（阶段 1）。

只在本文件内 import mujoco；对外只暴露 BaseEngine 约定与通用状态字典。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import mujoco

from config import settings
from core.engine_timeout import (
    is_past_deadline,
    make_deadline,
    resolve_engine_timeout_sec,
    timeout_sim_result,
)
from core.schemas import SimResult, TaskSpec
from plugins.engines.base import BaseEngine


class MujocoEngine(BaseEngine):
    """基于 MuJoCo 的真实物理步进适配器。"""

    def __init__(self) -> None:
        self._model_ref: str = ""
        self._model: mujoco.MjModel | None = None
        self._data: mujoco.MjData | None = None
        self._t: int = 0
        # run_task 期间的墙钟截止时刻；step 内协作检查（Windows 无 signal）
        self._run_deadline: float | None = None

    @property
    def name(self) -> str:
        return "mujoco_engine"

    @property
    def version(self) -> str:
        return str(getattr(mujoco, "__version__", "unknown"))

    def _resolve_model_path(self, model_ref: str) -> Path:
        """将 model_ref 解析为文件路径（基于 MODELS_DIR，避免写死盘符逻辑）。"""
        ref = (model_ref or "").strip()
        if not ref or ref in {"default", "builtin_arm2", "builtin"}:
            return settings.default_model_path()
        # 第13期接触试机场景（不改默认臂）
        if ref in {"builtin_arm2_contact", "contact", "arm2_contact"}:
            return (settings.MODELS_DIR / "builtin_arm2_contact" / "model.xml").resolve()

        path = Path(ref)
        if path.is_absolute():
            return path.resolve()

        # 相对路径一律相对 MODELS_DIR
        return (settings.MODELS_DIR / path).resolve()

    def _ensure_loaded(self) -> None:
        if self._model is None or self._data is None:
            self.load("default")

    def load(self, model_ref: str) -> None:
        path = self._resolve_model_path(model_ref)
        if not path.exists():
            raise FileNotFoundError(f"模型文件不存在: {path}")

        self._model = mujoco.MjModel.from_xml_path(str(path))
        self._data = mujoco.MjData(self._model)
        self._model_ref = str(path)
        self.reset()

    def reset(self) -> None:
        self._ensure_loaded()
        assert self._model is not None and self._data is not None
        mujoco.mj_resetData(self._model, self._data)
        self._t = 0
        mujoco.mj_forward(self._model, self._data)

    def _extract_control(self, control: dict[str, Any] | TaskSpec) -> tuple[list[float] | None, int, str]:
        """从 TaskSpec 或 dict 提取目标控制、子步数、动作名。"""
        if isinstance(control, TaskSpec):
            action = control.action or "move"
            params = control.params or {}
            nsub = int(params.get("nsub", 20))
            if action == "home":
                return [0.0] * max(1, self._model.nu if self._model else 1), nsub, action
            if action == "wait":
                # 保持当前控制，短暂停顿示意
                nsub = int(params.get("nsub", 5))
                assert self._data is not None and self._model is not None
                if self._model.nu > 0:
                    targets = [float(self._data.ctrl[i]) for i in range(self._model.nu)]
                else:
                    targets = [float(self._data.qpos[i]) for i in range(min(2, self._model.nq))]
                return targets, nsub, action
            if "joint_targets" in params:
                return [float(x) for x in params["joint_targets"]], nsub, action
            if "ctrl" in params:
                return [float(x) for x in params["ctrl"]], nsub, action
            # 默认：在当前 ctrl 上加一点偏置，保证能看见运动
            delta = float(params.get("joint_delta", 0.3))
            assert self._data is not None and self._model is not None
            base = [float(self._data.ctrl[i]) for i in range(self._model.nu)]
            if not base:
                base = [float(self._data.qpos[i]) for i in range(min(2, self._model.nq))]
            targets = [b + delta for b in base]
            if action == "grab":
                # 无场景时的关节示意；有场景时 joint_targets 由 planar_aim 注入
                if len(targets) >= 2:
                    targets[0] = 0.8
                    targets[1] = -0.6
            if action == "place" and "joint_targets" not in params and len(targets) >= 2:
                targets[0] = 0.5
                targets[1] = 0.4
            return targets, nsub, action

        action = str(control.get("action", "move"))
        nsub = int(control.get("nsub", 20))
        if "joint_targets" in control:
            return [float(x) for x in control["joint_targets"]], nsub, action
        if "ctrl" in control:
            return [float(x) for x in control["ctrl"]], nsub, action
        return None, nsub, action

    def step(self, control: dict[str, Any] | TaskSpec) -> dict[str, Any]:
        self._ensure_loaded()
        assert self._model is not None and self._data is not None

        targets, nsub, _action = self._extract_control(control)
        if targets is not None and self._model.nu > 0:
            for i in range(min(self._model.nu, len(targets))):
                self._data.ctrl[i] = targets[i]
        elif targets is not None and self._model.nu == 0 and self._model.nq > 0:
            # 无执行器时直接写 qpos（教学模型兜底）
            for i in range(min(self._model.nq, len(targets))):
                self._data.qpos[i] = targets[i]

        for _ in range(max(1, nsub)):
            if is_past_deadline(self._run_deadline):
                raise TimeoutError("ENGINE_TIMEOUT")
            mujoco.mj_step(self._model, self._data)

        self._t += 1
        return self.get_state()

    def get_state(self) -> dict[str, Any]:
        self._ensure_loaded()
        assert self._model is not None and self._data is not None
        nq = int(self._model.nq)
        nu = int(self._model.nu)
        return {
            "t": self._t,
            "model_ref": self._model_ref,
            "joint_positions": [float(self._data.qpos[i]) for i in range(nq)],
            "ctrl": [float(self._data.ctrl[i]) for i in range(nu)],
        }

    def run_task(self, task: TaskSpec) -> SimResult:
        timeout_sec = resolve_engine_timeout_sec(task.params)
        started_at = time.monotonic()
        self._run_deadline = make_deadline(timeout_sec)
        trajectory: list[dict[str, Any]] = []
        try:
            if self._model is None:
                # 优先用 task.params 里的 model_ref，否则默认内置臂
                model_ref = str((task.params or {}).get("model_ref", "default"))
                self.load(model_ref)

            trajectory = [self.get_state()]
            # 接触场景：记录物体初始位姿，供位移代理 + 朝物体示意
            object_before = None
            has_scene_obj = False
            try:
                from core.contact_probe import mujoco_object_xpos, mujoco_scene_has_object

                if self._model is not None and mujoco_scene_has_object(self._model):
                    has_scene_obj = True
                    object_before = mujoco_object_xpos(self._model, self._data)
            except Exception:
                object_before = None
                has_scene_obj = False

            from core.planar_aim import apply_scene_aim_to_task

            task, pose_m = apply_scene_aim_to_task(
                task, has_scene=has_scene_obj, object_xpos=object_before
            )

            steps = int((task.params or {}).get("steps", 5))
            if str(task.action or "") == "wait":
                steps = int((task.params or {}).get("steps", 1) or 1)
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

            moved = False
            if len(trajectory) >= 2:
                a = trajectory[0].get("joint_positions") or []
                b = trajectory[-1].get("joint_positions") or []
                moved = any(abs(float(x) - float(y)) > 1e-4 for x, y in zip(a, b))

            metrics: dict[str, Any] = {
                "steps": len(trajectory) - 1,
                "stable": 1.0 if moved else 0.5,
                "moved": moved,
                "elapsed_sec": max(0.0, time.monotonic() - started_at),
                "timeout_sec": timeout_sec,
            }
            # 第13期：接触/接近旁路（只增 metrics）
            try:
                from core.contact_probe import evaluate_mujoco_contact

                contact_m = evaluate_mujoco_contact(
                    self._model,
                    self._data,
                    action=str(task.action or ""),
                    object_xpos_before=object_before,
                )
                metrics.update(contact_m)
            except Exception:
                from core.contact_scene_contract import empty_contact_metrics

                metrics.update(empty_contact_metrics(has_scene=False))

            metrics.update(pose_m)

            return SimResult(
                task_id=task.task_id,
                ok=True,
                trajectory=trajectory,
                metrics=metrics,
                message=f"MuJoCo 已执行 action={task.action} target={task.target}",
                engine_name=self.name,
                engine_version=self.version,
            )
        except TimeoutError:
            return timeout_sim_result(
                task_id=task.task_id,
                timeout_sec=timeout_sec,
                started_at=started_at,
                trajectory=trajectory,
                engine_name=self.name,
                engine_version=self.version,
            )
        except Exception as exc:  # noqa: BLE001
            return SimResult(
                task_id=task.task_id,
                ok=False,
                trajectory=[],
                metrics={},
                message=f"仿真执行失败: {exc}",
                engine_name=self.name,
                engine_version=self.version,
            )
        finally:
            self._run_deadline = None

    def list_physics_params(self) -> dict[str, Any]:
        """读取白名单物理参数（通用键名，不暴露 MjModel 句柄）。"""
        self._ensure_loaded()
        assert self._model is not None

        frictions = [float(self._model.geom_friction[i][0]) for i in range(self._model.ngeom)]
        dampings = [float(self._model.dof_damping[i]) for i in range(self._model.nv)]

        range_mins: list[float] = []
        range_maxs: list[float] = []
        for j in range(self._model.njnt):
            # jnt_limited: 0/1；无限位时给宽默认值便于面板显示
            if int(self._model.jnt_limited[j]) == 1:
                range_mins.append(float(self._model.jnt_range[j][0]))
                range_maxs.append(float(self._model.jnt_range[j][1]))
            else:
                range_mins.append(-3.14)
                range_maxs.append(3.14)

        return {
            "friction": sum(frictions) / len(frictions) if frictions else 1.0,
            "joint_damping": sum(dampings) / len(dampings) if dampings else 0.0,
            "joint_range_min": min(range_mins) if range_mins else -2.8,
            "joint_range_max": max(range_maxs) if range_maxs else 2.8,
            "ngeom": int(self._model.ngeom),
            "nv": int(self._model.nv),
            "njnt": int(self._model.njnt),
        }

    def get_joint_limits(self) -> list[tuple[float, float]]:
        """逐关节限位（供安全闸）；不暴露 MjModel 句柄。"""
        self._ensure_loaded()
        assert self._model is not None
        out: list[tuple[float, float]] = []
        for j in range(self._model.njnt):
            if int(self._model.jnt_limited[j]) == 1:
                out.append((float(self._model.jnt_range[j][0]), float(self._model.jnt_range[j][1])))
            else:
                out.append((-3.14, 3.14))
        return out

    def set_physics_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """按白名单写回 MuJoCo 模型字段；未知键进入 skipped。"""
        self._ensure_loaded()
        assert self._model is not None and self._data is not None

        skipped: list[str] = []
        params = params or {}

        if "friction" in params:
            value = float(params["friction"])
            for i in range(self._model.ngeom):
                # 滑动摩擦为主；扭转/滚动保持相对比例或最小值
                old = self._model.geom_friction[i]
                self._model.geom_friction[i][0] = value
                self._model.geom_friction[i][1] = max(0.001, float(old[1]))
                self._model.geom_friction[i][2] = max(0.0001, float(old[2]))
        if "joint_damping" in params:
            value = float(params["joint_damping"])
            for i in range(self._model.nv):
                self._model.dof_damping[i] = value
        if "joint_range_min" in params or "joint_range_max" in params:
            cur = self.list_physics_params()
            rmin = float(params.get("joint_range_min", cur["joint_range_min"]))
            rmax = float(params.get("joint_range_max", cur["joint_range_max"]))
            if rmin > rmax:
                rmin, rmax = rmax, rmin
            for j in range(self._model.njnt):
                self._model.jnt_limited[j] = 1
                self._model.jnt_range[j][0] = rmin
                self._model.jnt_range[j][1] = rmax

        for key in params:
            if key not in {"friction", "joint_damping", "joint_range_min", "joint_range_max"}:
                skipped.append(str(key))

        # 参数改的是模型，重置数据使状态一致
        mujoco.mj_forward(self._model, self._data)
        out = self.list_physics_params()
        out["skipped"] = skipped
        return out
