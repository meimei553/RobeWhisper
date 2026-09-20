# -*- coding: utf-8 -*-
"""网站运行时：一份本机会话。页面只调这里，不直接碰仿真对象。"""
from __future__ import annotations

import threading
from typing import Any
from unittest.mock import patch

from config.safe import fresh_settings, setting
from core.bootstrap import create_engine, create_llm, create_robot
from core.browse_tables import experiences_table_rows, experiments_table_rows
from core.demo_pack import export_demo_pack
from core.instruction_guard import demo_instruction_samples
from core.model_catalog import list_model_options, save_uploaded_model
from core.pipeline import Pipeline
from frontend.capability_panel import (
    build_feature_switch_states,
    build_rsr_status_hint,
    build_system_status,
    capability_markdown,
    contact_scene_status_hint,
    diagnose_run_result,
    feature_catalog_items,
    format_diagnosis_for_chat,
    format_rsr_run_message,
    format_rsr_status_line,
    real_robot_safety_banner,
    rsr_policy_label,
    rsr_reference_source_label,
)
from frontend.reply_text import FRIENDLY_BLOCKED, format_fail_reply, format_success_reply
from plugins.engines.base import BaseEngine

_BLOCKED = FRIENDLY_BLOCKED


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class SiteRuntime:
    """单人本机站：一个仿真会话对应一个网页。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.engine: BaseEngine | None = None
        self.model_ref = "default"
        self.chat: list[dict[str, Any]] = []
        self.flow = {"model": False, "physics": False, "step": False}
        self.rsr_enable = False
        self.last_diagnosis: dict | None = None
        self.last_proxy: dict | None = None
        self.last_rsr: dict | None = None
        self.last_robot: dict | None = None
        self.engine_error = ""

    def init(self) -> None:
        fresh_settings()
        with self._lock:
            self.rsr_enable = bool(setting("USE_REAL_SIM_REAL", False))
            try:
                engine = create_engine()
                engine.load(self.model_ref)
                engine.reset()
                self.engine = engine
                self.flow["model"] = True
                self.engine_error = ""
            except Exception:
                self.engine = None
                self.engine_error = _BLOCKED

    def _engine(self) -> BaseEngine:
        if self.engine is None:
            raise RuntimeError("no-engine")
        return self.engine

    def _state_unlocked(self) -> dict[str, Any]:
        try:
            raw = _jsonable(self._engine().get_state())
        except Exception:
            raw = {"t": 0, "joint_positions": [], "model_ref": self.model_ref, "error": _BLOCKED}
        if not isinstance(raw, dict):
            raw = {"t": 0, "joint_positions": []}
        raw["flow"] = dict(self.flow)
        raw["model_ref"] = raw.get("model_ref") or self.model_ref
        return raw

    def _load_unlocked(self, ref: str) -> tuple[bool, str]:
        engine = self._engine()
        try:
            engine.load(ref)
            engine.reset()
            self.model_ref = ref
            self.flow["model"] = True
            self.flow["physics"] = False
            self.flow["step"] = False
            return True, "已加载：" + ref
        except Exception:
            try:
                engine.load("default")
                engine.reset()
                self.model_ref = "default"
                self.flow["model"] = True
                return False, "模型加载失败，已回退到默认内置臂。"
            except Exception:
                self.flow["model"] = False
                return False, _BLOCKED

    def _proxy_lines_unlocked(self) -> list[str]:
        if not isinstance(self.last_proxy, dict) or not self.last_proxy:
            return []
        from core.pose_grounding_contract import format_proxy_summary_lines
        return [str(x) for x in format_proxy_summary_lines(self.last_proxy)]

    def _rsr_view_unlocked(self) -> dict[str, Any]:
        last = self.last_rsr if isinstance(self.last_rsr, dict) else None
        if not last:
            return {"has_result": False, "enabled": self.rsr_enable}
        dev = last.get("deviation") or {}
        cal = last.get("calibration") or {}
        src_raw = last.get("reference_source")
        src_label = rsr_reference_source_label(src_raw) if src_raw else ("跳过" if last.get("skipped") else "—")
        return {
            "has_result": True,
            "enabled": self.rsr_enable,
            "message": last.get("message"),
            "source_label": src_label,
            "mae": dev.get("mae"),
            "updated": bool(cal.get("updated")),
            "frames": last.get("reference_frame_count"),
            "policy": rsr_policy_label(
                last.get("policy"),
                require_real=bool(last.get("require_real_trajectory")) if "require_real_trajectory" in last else None,
            ),
            "before": cal.get("before"),
            "after": cal.get("after"),
        }

    def overview(self) -> dict[str, Any]:
        fresh_settings()
        with self._lock:
            robot = create_robot()
            from config import settings as settings_mod
            llm_effective = str(getattr(settings_mod, "effective_llm_backend", lambda: setting("LLM_BACKEND", "mock"))())
            llm_note = str(getattr(settings_mod, "llm_config_note", lambda: "")())
            use_real = bool(setting("USE_REAL_ROBOT", False))
            robot_backend = str(setting("ROBOT_BACKEND", "mock"))
            endpoint = str(setting("ROBOT_EXECUTE_ENDPOINT", "") or "")
            status = build_system_status(
                llm_backend=llm_effective,
                engine_backend=str(setting("ENGINE_BACKEND", "mujoco")),
                robot_backend=robot_backend,
                use_real_robot=use_real,
                use_rsr_config=bool(setting("USE_REAL_SIM_REAL", False)),
                rsr_ui=self.rsr_enable,
                robot_name=str(getattr(robot, "name", "")),
                model_ref=self.model_ref,
                engine_ok=self.engine is not None,
                llm_config_note=llm_note,
                robot_endpoint=endpoint,
            )
            banner = status.get("real_robot_banner") or real_robot_safety_banner(
                use_real_robot=use_real,
                robot_backend=robot_backend,
                robot_name=str(getattr(robot, "name", "")),
                robot_endpoint=endpoint,
            )
            switches = build_feature_switch_states(
                use_real_robot=use_real,
                robot_backend=robot_backend,
                robot_endpoint=endpoint,
                robot_name=str(getattr(robot, "name", "")),
                llm_backend_wanted=str(setting("LLM_BACKEND", "mock") or "mock"),
                llm_backend_effective=llm_effective,
                llm_api_configured=bool(getattr(settings_mod, "llm_api_configured", lambda: False)()),
                use_rsr_config=bool(setting("USE_REAL_SIM_REAL", False)),
                rsr_ui=self.rsr_enable,
            )
            rsr_require = bool(setting("RSR_REQUIRE_REAL_TRAJECTORY", False))
            rsr_hint = build_rsr_status_hint(
                rsr_enabled=self.rsr_enable,
                last_rsr=self.last_rsr if isinstance(self.last_rsr, dict) else None,
                require_real_config=rsr_require,
            )
            physics = {}
            if self.engine is not None:
                try:
                    physics = _jsonable(self.engine.list_physics_params())
                except Exception:
                    physics = {}
            return _jsonable({
                "ok": self.engine is not None,
                "title": "RobeWhisper机器人自然语言编程平台",
                "caption": "前后端已分开。功能分成四类：自然语言、模型与物理、实验与经验、能力与诊断。",
                "hint": "推荐先在「自然语言」点一个样例。默认不连真机，失败时页面只给友好提示。",
                "engine_error": self.engine_error,
                "banner": banner,
                "ready": bool(status.get("ready")),
                "ok_items": status.get("ok_items") or [],
                "issues": status.get("issues") or [],
                "capabilities_md": capability_markdown(llm_effective),
                "catalog": feature_catalog_items(),
                "switches": switches,
                "samples": demo_instruction_samples(),
                "contact": contact_scene_status_hint(self.model_ref),
                "rsr_enable": self.rsr_enable,
                "rsr_line": format_rsr_status_line(rsr_hint).replace("**", ""),
                "rsr_level": rsr_hint.get("level") or "info",
                "rsr_policy": rsr_policy_label("require_real" if rsr_require else "prefer_real", require_real=rsr_require),
                "llm_backend": setting("LLM_BACKEND", "mock"),
                "llm_effective": llm_effective,
                "robot_backend": robot_backend,
                "use_real_robot": use_real,
                "model_ref": self.model_ref,
                "models": list_model_options(),
                "state": self._state_unlocked() if self.engine else {"t": 0, "joint_positions": [], "flow": dict(self.flow)},
                "physics": physics,
                "diagnosis": self.last_diagnosis,
                "proxy": self._proxy_lines_unlocked(),
                "chat": list(self.chat),
                "rsr": self._rsr_view_unlocked(),
            })

    def set_rsr(self, enabled: bool) -> dict[str, Any]:
        with self._lock:
            self.rsr_enable = bool(enabled)
        return {"ok": True, "rsr_enable": self.rsr_enable}

    def _append_chat(self, role: str, content: str, meta: dict | None = None) -> None:
        self.chat.append({"role": role, "content": content, "meta": _jsonable(meta or {})})
        if len(self.chat) > 40:
            self.chat = self.chat[-40:]

    def _record_result_unlocked(self, result: Any, *, experience_hit_override: bool | None, demo: str = "") -> None:
        data = result.data if isinstance(result.data, dict) else {}
        spec = data.get("task_spec") if isinstance(data.get("task_spec"), dict) else {}
        sim = data.get("sim_result") if isinstance(data.get("sim_result"), dict) else {}
        gate = data.get("safety_gate") if isinstance(data.get("safety_gate"), dict) else None
        hit = bool(data.get("experience_hit")) if experience_hit_override is None else experience_hit_override
        if result.ok:
            exp_meta = data.get("experiment") or {}
            robot_meta = data.get("robot_result") if isinstance(data.get("robot_result"), dict) else {}
            rsr_meta = data.get("rsr") if isinstance(data.get("rsr"), dict) else None
            adapters = data.get("adapters") or {}
            from core.contact_scene_contract import format_contact_trial_message
            from core.multi_step_contract import format_multi_step_message
            from core.pose_grounding_contract import build_proxy_summary, format_pose_grounding_message
            metrics = sim.get("metrics") if isinstance(sim.get("metrics"), dict) else {}
            multi_meta = data.get("multi_step") if isinstance(data.get("multi_step"), dict) else None
            diag = diagnose_run_result(
                ok=True, code=result.code, message=result.message, task_spec=spec, sim_result=sim,
                robot_result=robot_meta, rsr=rsr_meta, safety_gate=gate, experience_hit=hit,
                llm_backend=str(setting("LLM_BACKEND", "mock")),
                use_real_robot=bool(setting("USE_REAL_ROBOT", False)), multi_step=multi_meta,
            )
            self.last_diagnosis = diag
            self.last_proxy = build_proxy_summary(metrics=metrics, multi_step=multi_meta, rsr=rsr_meta)
            self.last_robot = robot_meta
            self.last_rsr = rsr_meta
            self.flow["step"] = True
            action = str(spec.get("action") or ("grab" if demo == "overlimit" else ""))
            target = str(spec.get("target") or ("red_block" if demo == "overlimit" else ""))
            reply = format_success_reply(
                result.message, action=action, target=target,
                frame_count=len(sim.get("trajectory") or []), experience_hit=hit,
                experiment_id=str((exp_meta or {}).get("experiment_id") or ""),
                robot_name=str(adapters.get("robot") or ""),
                robot_msg=str(robot_meta.get("message") or ""),
                rsr_msg="未执行（演示）" if demo == "overlimit" else format_rsr_run_message(rsr_meta, enabled=self.rsr_enable),
                contact_msg=format_contact_trial_message(metrics),
                multi_step_msg=format_multi_step_message(spec, metrics, multi_meta),
                pose_msg=format_pose_grounding_message(metrics),
                diagnosis=format_diagnosis_for_chat(diag),
            )
            self._append_chat("assistant", reply, {"task_spec": spec, "safety_gate": gate, "demo": demo})
        else:
            diag = diagnose_run_result(
                ok=False, code=result.code, message=result.message, task_spec=spec or None,
                sim_result=sim or None, safety_gate=gate, experience_hit=hit,
                llm_backend=str(setting("LLM_BACKEND", "mock")),
                use_real_robot=bool(setting("USE_REAL_ROBOT", False)),
                multi_step=data.get("multi_step") if isinstance(data.get("multi_step"), dict) else None,
            )
            self.last_diagnosis = diag
            self._append_chat("assistant", format_fail_reply(result.message, result.code, diagnosis=format_diagnosis_for_chat(diag)), {"code": result.code, "demo": demo})

    def run_text(self, text: str) -> dict[str, Any]:
        text = (text or "").strip()
        if not text:
            return {"ok": False, "message": "请先输入一句指令，或点一个样例。"}
        with self._lock:
            if self.engine is None:
                return {"ok": False, "message": self.engine_error or _BLOCKED}
            self._append_chat("user", text)
            try:
                pipeline = Pipeline(llm=create_llm(), engine=self.engine, robot=create_robot())
                result = pipeline.run_instruction(text, model_ref=self.model_ref, real_sim_real=self.rsr_enable)
                self._record_result_unlocked(result, experience_hit_override=None)
            except Exception:
                diag = diagnose_run_result(ok=False, code="INTERNAL", message=_BLOCKED, llm_backend=str(setting("LLM_BACKEND", "mock")))
                self.last_diagnosis = diag
                self._append_chat("assistant", format_fail_reply(_BLOCKED, "INTERNAL", diagnosis=format_diagnosis_for_chat(diag)), {"code": "INTERNAL"})
            return {"ok": True, "chat": list(self.chat), "diagnosis": self.last_diagnosis, "state": self._state_unlocked(), "rsr": self._rsr_view_unlocked(), "proxy": self._proxy_lines_unlocked()}

    def run_overlimit_demo(self) -> dict[str, Any]:
        with self._lock:
            if self.engine is None:
                return {"ok": False, "message": self.engine_error or _BLOCKED}
            self._append_chat("user", "【演示】抓起红色积木（故意超大关节目标）")
            try:
                pipeline = Pipeline(llm=create_llm(), engine=self.engine, robot=create_robot())
                huge = {"ok": True, "suggested_joint_targets": [9.0, -9.0]}
                with patch("core.pipeline.find_experience", return_value=huge):
                    with patch("core.pipeline.mark_experience_used"):
                        result = pipeline.run_instruction("抓起红色积木", model_ref=self.model_ref, real_sim_real=False)
                self._record_result_unlocked(result, experience_hit_override=True, demo="overlimit")
            except Exception:
                self._append_chat("assistant", format_fail_reply(_BLOCKED, "INTERNAL"), {"code": "INTERNAL"})
            return {"ok": True, "chat": list(self.chat), "diagnosis": self.last_diagnosis}

    def clear_chat(self) -> dict[str, Any]:
        with self._lock:
            self.chat = []
        return {"ok": True}

    def load_model(self, ref: str) -> dict[str, Any]:
        with self._lock:
            if self.engine is None:
                return {"ok": False, "message": self.engine_error or _BLOCKED}
            ok, message = self._load_unlocked(ref or "default")
            return {"ok": ok, "message": message, "model_ref": self.model_ref, "state": self._state_unlocked(), "contact": contact_scene_status_hint(self.model_ref)}

    def upload_model(self, filename: str, data: bytes) -> dict[str, Any]:
        saved = save_uploaded_model(filename, data)
        if str(saved.get("ok")) != "true":
            return {"ok": False, "message": saved.get("message") or _BLOCKED}
        loaded = self.load_model(str(saved.get("ref") or "default"))
        if loaded.get("ok"):
            loaded["message"] = str(saved.get("message") or loaded.get("message"))
        return loaded

    def apply_physics(self, params: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self.engine is None:
                return {"ok": False, "message": self.engine_error or _BLOCKED}
            try:
                applied = self.engine.set_physics_params({
                    "friction": float(params.get("friction", 1.0)),
                    "joint_damping": float(params.get("joint_damping", 0.5)),
                    "joint_range_min": float(params.get("joint_range_min", -2.8)),
                    "joint_range_max": float(params.get("joint_range_max", 2.8)),
                })
                self.flow["physics"] = True
                return {"ok": True, "message": "物理参数已写入引擎", "physics": _jsonable(applied), "state": self._state_unlocked()}
            except Exception:
                return {"ok": False, "message": _BLOCKED}

    def step(self, targets: list[float]) -> dict[str, Any]:
        with self._lock:
            if self.engine is None:
                return {"ok": False, "message": self.engine_error or _BLOCKED}
            try:
                state = _jsonable(self.engine.step({"action": "move", "joint_targets": [float(x) for x in targets], "nsub": 40}))
                self.flow["step"] = True
                if isinstance(state, dict):
                    state["flow"] = dict(self.flow)
                return {"ok": True, "message": "已完成一步仿真", "state": state}
            except Exception:
                return {"ok": False, "message": _BLOCKED, "state": self._state_unlocked()}

    def reset_sim(self) -> dict[str, Any]:
        with self._lock:
            if self.engine is None:
                return {"ok": False, "message": self.engine_error or _BLOCKED}
            try:
                self.engine.reset()
                self.flow["step"] = False
                return {"ok": True, "message": "已重置到初始状态", "state": self._state_unlocked()}
            except Exception:
                return {"ok": False, "message": _BLOCKED}

    def reload_model(self) -> dict[str, Any]:
        return self.load_model(self.model_ref)

    def records(self) -> dict[str, Any]:
        return {"ok": True, "experiments": experiments_table_rows(8), "experiences": experiences_table_rows(8)}

    def export_pack(self, experiment_id: str, latest: bool) -> dict[str, Any]:
        ident = (experiment_id or "").strip()
        pack = export_demo_pack(ident or None, latest=bool(latest) or not ident)
        data = _jsonable(pack)
        name = ""
        if isinstance(data, dict) and data.get("zip_path"):
            from pathlib import Path
            name = Path(str(data["zip_path"])).name
        if isinstance(data, dict):
            data["download_name"] = name
        return data

    def probe_http(self) -> dict[str, Any]:
        from core.robot_bridge_probe import probe_http_bridge
        return _jsonable(probe_http_bridge(timeout_sec=3.0))

    def probe_llm(self) -> dict[str, Any]:
        from core.llm_api_probe import probe_llm_api
        return _jsonable(probe_llm_api(timeout_sec=8.0))


RUNTIME = SiteRuntime()