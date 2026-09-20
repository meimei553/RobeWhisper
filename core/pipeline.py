# -*- coding: utf-8 -*-
"""
编排层：自然语言 → TaskSpec → 引擎执行 → 实验落盘 / 经验复用。
"""

from __future__ import annotations

import uuid

from core.engine_timeout import (
    ENGINE_TIMEOUT_CODE,
    FRIENDLY_ENGINE_TIMEOUT,
    is_timeout_result,
)
from core.experience_store import find_experience, mark_experience_used, remember_experience
from core.experiment_store import build_experiment_record, save_experiment
from core.rsr_loop import run_rsr_iteration
from core.safety_gate import apply_safety_gate, merge_gate_into_params
from core.schemas import ApiResult, TaskSpec
from plugins.engines.base import BaseEngine
from plugins.llm.base import BaseLLM
from plugins.robot.base import BaseRobot

FRIENDLY_INTERNAL = "思考遇到一些阻碍，请稍后再试。"
SAFETY_REJECT_CODE = "SAFETY_REJECTED"


class Pipeline:
    """依赖注入：构造时传入任意符合基类的实现。"""

    def __init__(self, llm: BaseLLM, engine: BaseEngine, robot: BaseRobot) -> None:
        self._llm = llm
        self._engine = engine
        self._robot = robot

    def _adapter_names(self) -> dict[str, str]:
        return {
            "llm": self._llm.name,
            "engine": self._engine.name,
            "robot": self._robot.name,
        }

    def _build_record(
        self,
        *,
        raw_text: str,
        task_spec: dict | None,
        sim_result: dict | None,
        ok: bool,
        code: str,
        message: str,
        experience_hit: bool = False,
        model_ref: str = "default",
        snapshot_extra: dict | None = None,
        robot_result: dict | None = None,
    ) -> dict:
        """统一落盘组装：自动带 run_snapshot（第 10 期）与 robot_result（第 11 期）。"""
        return build_experiment_record(
            raw_text=raw_text,
            task_spec=task_spec,
            sim_result=sim_result,
            ok=ok,
            code=code,
            message=message,
            adapters=self._adapter_names(),
            experience_hit=experience_hit,
            model_ref=model_ref,
            llm=self._llm,
            engine=self._engine,
            robot=self._robot,
            snapshot_extra=snapshot_extra,
            robot_result=robot_result,
        )

    def run_instruction(
        self,
        text: str,
        model_ref: str = "default",
        *,
        execute_robot: bool = True,
        save_data: bool = True,
        real_sim_real: bool | None = None,
    ) -> ApiResult:
        """
        自然语言 → TaskSpec → 当前引擎仿真执行。

        real_sim_real:
          None → 读配置 USE_REAL_SIM_REAL（默认 false）
          True/False → 覆盖配置，成功后可选做一次 RSR 校准
        """
        task_id = uuid.uuid4().hex[:12]
        experience_hit = False
        try:
            from config.safe import setting

            rsr_enabled = (
                bool(setting("USE_REAL_SIM_REAL", False))
                if real_sim_real is None
                else bool(real_sim_real)
            )
            rsr_gain = float(setting("RSR_CALIB_GAIN", 0.5) or 0.5)
            rsr_require_real = bool(setting("RSR_REQUIRE_REAL_TRAJECTORY", False))
            parse_result = self._llm.parse_instruction(text, task_id=task_id)
            if not parse_result.ok or not parse_result.data:
                if save_data:
                    rec = self._build_record(
                        raw_text=text,
                        task_spec=None,
                        sim_result=None,
                        ok=False,
                        code=parse_result.code,
                        message=parse_result.message,
                        model_ref=model_ref,
                    )
                    saved = save_experiment(rec)
                    data = dict(parse_result.data or {})
                    data["experiment"] = saved
                    return ApiResult.fail(parse_result.code, parse_result.message, data=data)
                return parse_result

            spec = TaskSpec.from_dict(parse_result.data.get("task_spec") or {})
            if not spec.action:
                return ApiResult.fail("PARSE_FAILED", FRIENDLY_INTERNAL)

            # 经验优先：仅单步任务注入（多步暂不复用，避免跨步污染）
            ref = str((spec.params or {}).get("model_ref") or model_ref or "default")
            from core.multi_step_contract import is_multi_step

            multi = is_multi_step(spec.steps)
            if not multi:
                exp = find_experience(spec.action, spec.target, model_ref=ref)
                if exp and exp.get("suggested_joint_targets"):
                    experience_hit = True
                    spec.params = dict(spec.params or {})
                    if "joint_targets" not in spec.params:
                        spec.params["joint_targets"] = list(exp["suggested_joint_targets"])
                    mark_experience_used(spec.action, spec.target, model_ref=ref)

            self._engine.load(ref)
            self._engine.reset()

            # 安全闸（第 9 期）：执行前裁剪/拒绝；保留 original 不堵死真机对照
            safety_mode = str(setting("SAFETY_MODE", "clip") or "clip")
            joint_limits = None
            getter = getattr(self._engine, "get_joint_limits", None)
            if callable(getter):
                try:
                    joint_limits = getter()
                except Exception:
                    joint_limits = None

            from core.multi_step_exec import (
                annotate_step_metrics,
                iter_step_specs,
                merge_step_sim_results,
            )

            gate: dict
            if multi:
                step_specs = iter_step_specs(spec)
                step_sims = []
                step_gates: list[dict] = []
                for i, step_spec in enumerate(step_specs):
                    gate_i = apply_safety_gate(
                        step_spec, joint_limits=joint_limits, mode=safety_mode
                    )
                    step_gates.append(gate_i)
                    if not gate_i.get("ok"):
                        data_fail = {
                            "task_spec": spec.to_dict(),
                            "safety_gate": gate_i,
                            "experience_hit": experience_hit,
                            "multi_step": {"failed_at": i + 1, "total": len(step_specs)},
                        }
                        msg = f"第 {i + 1}/{len(step_specs)} 步被安全闸拦截：" + str(
                            gate_i.get("message") or "安全闸拒绝执行"
                        )
                        if save_data:
                            rec = self._build_record(
                                raw_text=text,
                                task_spec=spec.to_dict(),
                                sim_result=None,
                                ok=False,
                                code=SAFETY_REJECT_CODE,
                                message=msg,
                                experience_hit=experience_hit,
                                model_ref=ref,
                                snapshot_extra={"step_count": len(step_specs), "failed_at": i + 1},
                            )
                            rec["safety_gate"] = gate_i
                            data_fail["experiment"] = save_experiment(rec)
                        return ApiResult.fail(SAFETY_REJECT_CODE, msg, data=data_fail)
                    step_spec.params = merge_gate_into_params(step_spec.params, gate_i)
                    sim_i = self._engine.run_task(step_spec)
                    sim_i = annotate_step_metrics(
                        sim_i,
                        action=step_spec.action,
                        step_index=i + 1,
                        step_total=len(step_specs),
                    )
                    if not sim_i.ok:
                        fail_code = ENGINE_TIMEOUT_CODE if is_timeout_result(sim_i) else "INTERNAL"
                        fail_msg = (
                            f"第 {i + 1}/{len(step_specs)} 步执行失败"
                            + (
                                f"：{FRIENDLY_ENGINE_TIMEOUT}"
                                if fail_code == ENGINE_TIMEOUT_CODE
                                else ""
                            )
                        )
                        if save_data:
                            rec = self._build_record(
                                raw_text=text,
                                task_spec=spec.to_dict(),
                                sim_result=sim_i.to_dict(),
                                ok=False,
                                code=fail_code,
                                message=fail_msg,
                                experience_hit=experience_hit,
                                model_ref=ref,
                                snapshot_extra={"step_count": len(step_specs), "failed_at": i + 1},
                            )
                            rec["safety_gate"] = gate_i
                            saved = save_experiment(rec)
                            return ApiResult.fail(
                                fail_code,
                                fail_msg,
                                data={
                                    "task_spec": spec.to_dict(),
                                    "sim_result": sim_i.to_dict(),
                                    "adapters": self._adapter_names(),
                                    "experience_hit": experience_hit,
                                    "safety_gate": gate_i,
                                    "multi_step": {"failed_at": i + 1, "total": len(step_specs)},
                                    "experiment": saved,
                                },
                            )
                        return ApiResult.fail(
                            fail_code,
                            fail_msg,
                            data={
                                "task_spec": spec.to_dict(),
                                "sim_result": sim_i.to_dict(),
                                "multi_step": {"failed_at": i + 1, "total": len(step_specs)},
                            },
                        )
                    step_sims.append(sim_i)

                sim = merge_step_sim_results(
                    parent_task_id=spec.task_id,
                    step_results=step_sims,
                    engine_name=self._engine.name,
                    engine_version=getattr(self._engine, "version", "0"),
                )
                gate = {
                    "ok": True,
                    "message": "多步安全闸逐步通过",
                    "multi_step_gates": step_gates,
                    "safety_audit": {"clipped": any(
                        (g.get("safety_audit") or {}).get("clipped") for g in step_gates
                    )},
                }
            else:
                gate = apply_safety_gate(spec, joint_limits=joint_limits, mode=safety_mode)
                if not gate.get("ok"):
                    data_fail = {
                        "task_spec": spec.to_dict(),
                        "safety_gate": gate,
                        "experience_hit": experience_hit,
                    }
                    if save_data:
                        rec = self._build_record(
                            raw_text=text,
                            task_spec=spec.to_dict(),
                            sim_result=None,
                            ok=False,
                            code=SAFETY_REJECT_CODE,
                            message=str(gate.get("message") or "安全闸拒绝执行"),
                            experience_hit=experience_hit,
                            model_ref=ref,
                        )
                        rec["safety_gate"] = gate
                        data_fail["experiment"] = save_experiment(rec)
                    return ApiResult.fail(
                        SAFETY_REJECT_CODE,
                        str(gate.get("message") or "安全闸拒绝执行"),
                        data=data_fail,
                    )
                spec.params = merge_gate_into_params(spec.params, gate)
                sim = self._engine.run_task(spec)

            adapters = self._adapter_names()

            if not sim.ok:
                fail_code = ENGINE_TIMEOUT_CODE if is_timeout_result(sim) else "INTERNAL"
                fail_msg = FRIENDLY_ENGINE_TIMEOUT if fail_code == ENGINE_TIMEOUT_CODE else FRIENDLY_INTERNAL
                if save_data:
                    remember_experience(
                        action=spec.action,
                        target=spec.target,
                        raw_text=text,
                        trajectory=list(sim.trajectory or []),
                        ok=False,
                        reason=sim.message or "sim_failed",
                        params=spec.params,
                        model_ref=ref,
                    )
                    rec = self._build_record(
                        raw_text=text,
                        task_spec=spec.to_dict(),
                        sim_result=sim.to_dict(),
                        ok=False,
                        code=fail_code,
                        message=fail_msg,
                        experience_hit=experience_hit,
                        model_ref=ref,
                    )
                    rec["safety_gate"] = gate
                    saved = save_experiment(rec)
                    return ApiResult.fail(
                        fail_code,
                        fail_msg,
                        data={
                            "task_spec": spec.to_dict(),
                            "sim_result": sim.to_dict(),
                            "adapters": adapters,
                            "experience_hit": experience_hit,
                            "safety_gate": gate,
                            "experiment": saved,
                        },
                    )
                return ApiResult.fail(
                    fail_code,
                    fail_msg,
                    data={
                        "task_spec": spec.to_dict(),
                        "sim_result": sim.to_dict(),
                        "adapters": adapters,
                        "safety_gate": gate,
                    },
                )

            robot_result = None
            if execute_robot:
                if multi:
                    # 真机默认逐步送单（简单、易定位第几步失败）
                    from core.schemas import ApiResult as _AR

                    step_specs = iter_step_specs(spec)
                    robot_parts = []
                    for i, step_spec in enumerate(step_specs):
                        rr = self._robot.execute_task(step_spec)
                        robot_parts.append(rr.to_dict())
                        if not rr.ok:
                            data_robot_fail = {
                                "task_spec": spec.to_dict(),
                                "sim_result": sim.to_dict(),
                                "robot_result": rr.to_dict(),
                                "adapters": adapters,
                                "experience_hit": experience_hit,
                                "safety_gate": gate,
                                "multi_step": {"failed_at": i + 1, "total": len(step_specs)},
                            }
                            msg = f"第 {i + 1}/{len(step_specs)} 步真机发送失败：" + str(rr.message)
                            if save_data:
                                rec = self._build_record(
                                    raw_text=text,
                                    task_spec=spec.to_dict(),
                                    sim_result=sim.to_dict(),
                                    ok=False,
                                    code=rr.code,
                                    message=msg,
                                    experience_hit=experience_hit,
                                    model_ref=ref,
                                    robot_result=rr.to_dict(),
                                    snapshot_extra={"step_count": len(step_specs), "failed_at": i + 1},
                                )
                                rec["safety_gate"] = gate
                                data_robot_fail["experiment"] = save_experiment(rec)
                                data_robot_fail["run_snapshot"] = rec.get("run_snapshot")
                            return ApiResult.fail(rr.code, msg, data=data_robot_fail)
                    robot_result = _AR.success(
                        f"多步真机已逐步发送 {len(step_specs)} 步",
                        data={"steps": robot_parts, "step_count": len(step_specs)},
                    )
                else:
                    robot_result = self._robot.execute_task(spec)
                    if not robot_result.ok:
                        # 第 11 期：真机失败也落盘旁路，便于答辩展示「发过真机」
                        data_robot_fail = {
                            "task_spec": spec.to_dict(),
                            "sim_result": sim.to_dict(),
                            "robot_result": robot_result.to_dict(),
                            "adapters": adapters,
                            "experience_hit": experience_hit,
                            "safety_gate": gate,
                        }
                        if save_data:
                            rec = self._build_record(
                                raw_text=text,
                                task_spec=spec.to_dict(),
                                sim_result=sim.to_dict(),
                                ok=False,
                                code=robot_result.code,
                                message=robot_result.message,
                                experience_hit=experience_hit,
                                model_ref=ref,
                                robot_result=robot_result.to_dict(),
                            )
                            rec["safety_gate"] = gate
                            data_robot_fail["experiment"] = save_experiment(rec)
                            data_robot_fail["run_snapshot"] = rec.get("run_snapshot")
                        return ApiResult.fail(
                            robot_result.code,
                            robot_result.message,
                            data=data_robot_fail,
                        )

            # 成功：记经验（多步暂不写入经验，避免半段键）
            if save_data and not multi:
                remember_experience(
                    action=spec.action,
                    target=spec.target,
                    raw_text=text,
                    trajectory=list(sim.trajectory or []),
                    ok=True,
                    reason="",
                    params=spec.params,
                    model_ref=ref,
                )

            data: dict = {
                "task_spec": spec.to_dict(),
                "sim_result": sim.to_dict(),
                "adapters": adapters,
                "experience_hit": experience_hit,
                "safety_gate": gate,
            }
            if multi:
                data["multi_step"] = {
                    "step_count": int((sim.metrics or {}).get("step_count") or len(spec.steps)),
                    "step_actions": list((sim.metrics or {}).get("step_actions") or []),
                }
            if robot_result is not None:
                data["robot_result"] = robot_result.to_dict()

            # Real-Sim-Real：默认关；开启后真轨迹优先，无则按策略伪对照或跳过
            if rsr_enabled:
                try:
                    data["rsr"] = run_rsr_iteration(
                        self._engine,
                        list(sim.trajectory or []),
                        data.get("robot_result"),
                        gain=rsr_gain,
                        require_real_trajectory=rsr_require_real,
                    )
                except Exception:
                    data["rsr"] = {
                        "ok": False,
                        "skipped": True,
                        "message": FRIENDLY_INTERNAL,
                        "policy": "prefer_real",
                        "reference_frame_count": 0,
                    }

            if save_data:
                snap_extra = None
                if isinstance(data.get("rsr"), dict):
                    snap_extra = {
                        "rsr_enabled": True,
                        "rsr_reference_source": data["rsr"].get("reference_source"),
                        "rsr_policy": data["rsr"].get("policy"),
                        "rsr_reference_frame_count": data["rsr"].get("reference_frame_count"),
                    }
                # 接触试机旁路摘要（只增）
                sim_dict = data.get("sim_result") if isinstance(data.get("sim_result"), dict) else {}
                sim_m = sim_dict.get("metrics") if isinstance(sim_dict.get("metrics"), dict) else {}
                if sim_m.get("grasp_proxy") is not None or sim_m.get("contact_scene") is not None:
                    if snap_extra is None:
                        snap_extra = {}
                    snap_extra["grasp_proxy"] = sim_m.get("grasp_proxy")
                    snap_extra["contact_scene"] = sim_m.get("contact_scene")
                    snap_extra["contact_detected"] = sim_m.get("contact_detected")
                if multi:
                    if snap_extra is None:
                        snap_extra = {}
                    snap_extra["step_count"] = int((sim.metrics or {}).get("step_count") or len(spec.steps))
                    snap_extra["multi_step"] = True
                try:
                    from core.pose_grounding_contract import build_proxy_summary

                    if snap_extra is None:
                        snap_extra = {}
                    snap_extra["proxy_summary"] = build_proxy_summary(
                        metrics=sim_m,
                        multi_step=data.get("multi_step") if isinstance(data.get("multi_step"), dict) else None,
                        rsr=data.get("rsr") if isinstance(data.get("rsr"), dict) else None,
                    )
                    if sim_m.get("pose_source") is not None:
                        snap_extra["pose_source"] = sim_m.get("pose_source")
                except Exception:
                    pass
                rec = self._build_record(
                    raw_text=text,
                    task_spec=spec.to_dict(),
                    sim_result=sim.to_dict(),
                    ok=True,
                    code="OK",
                    message="指令已在虚拟引擎中执行",
                    experience_hit=experience_hit,
                    model_ref=ref,
                    snapshot_extra=snap_extra,
                    robot_result=robot_result.to_dict() if robot_result is not None else None,
                )
                if data.get("rsr"):
                    rec["rsr"] = data["rsr"]
                rec["safety_gate"] = gate
                data["experiment"] = save_experiment(rec)
                data["run_snapshot"] = rec.get("run_snapshot")

            msg = "指令已在虚拟引擎中执行"
            if multi and isinstance(sim.metrics, dict) and sim.metrics.get("step_count"):
                msg = str(sim.message or f"已按序执行 {sim.metrics.get('step_count')} 步试机")
            if experience_hit:
                msg = "已复用历史成功经验并完成执行"
            if gate.get("safety_audit", {}).get("clipped"):
                msg = msg + "；安全闸已裁剪超限关节目标"
            if rsr_enabled and isinstance(data.get("rsr"), dict) and data["rsr"].get("ok"):
                msg = msg + "；已执行 Real-Sim-Real 校准"
            return ApiResult.success(msg, data=data)
        except Exception:
            return ApiResult.fail("INTERNAL", FRIENDLY_INTERNAL)
