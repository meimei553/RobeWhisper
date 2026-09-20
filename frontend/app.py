# -*- coding: utf-8 -*-
"""
RobeWhisper 临时网站入口（阶段 7 · 产品化展示）

启动：
  streamlit run frontend/app.py --server.address 127.0.0.1 --server.port 8501
  或双击项目根目录「一键启动网站.bat」
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import settings
from config.safe import fresh_settings, setting
from core.bootstrap import create_engine, create_llm, create_robot
from core.browse_tables import experiences_table_rows, experiments_table_rows
from core.experience_store import list_experiences
from core.experiment_store import list_recent_experiments
from core.model_catalog import list_model_options, save_uploaded_model
from core.instruction_guard import demo_instruction_samples
from core.pipeline import Pipeline
from frontend.capability_panel import (
    build_feature_switch_states,
    build_rsr_status_hint,
    build_system_status,
    capability_markdown,
    contact_scene_status_hint,
    diagnose_run_result,
    feature_catalog_markdown,
    format_diagnosis_for_chat,
    format_feature_switch_line,
    format_rsr_run_message,
    format_rsr_status_line,
    real_robot_safety_banner,
    rsr_policy_label,
    rsr_reference_source_label,
    safety_demo_markdown,
)
from frontend.reply_text import FRIENDLY_BLOCKED, format_fail_reply, format_success_reply
from plugins.engines.base import BaseEngine


# Streamlit 热重载常留下半旧 settings；页面入口强制刷新一次
settings = fresh_settings()


st.set_page_config(
    page_title="RobeWhisper机器人自然语言编程平台",
    page_icon="🤖",
    layout="centered",
)

st.title("RobeWhisper机器人自然语言编程平台")
st.caption("产品化演示站 · 阶段 0–6 能力已打通（仿真 / 自然语言 / 实验经验 / 真机预留 / 可选校准）")

st.info(
    "推荐用法：下方输入一句中文指令 → 系统解析并在虚拟机械臂上执行。"
    "默认不连真机、不强制校准。成功轨迹会记入经验库；可在本页查看实验与校准摘要。"
)
with st.expander("已具备能力一览（阶段 0–6）", expanded=False):
    st.markdown(
        "- **模型与仿真**：导入/切换机械臂模型，调节摩擦、阻尼等物理参数\n"
        "- **自然语言**：中文指令 → TaskSpec → 虚拟执行\n"
        "- **实验与经验**：自动导出实验；相似成功动作可复用\n"
        "- **真机预留**：HTTP / ROS 桥（默认关闭，需显式开启）\n"
        "- **Real-Sim-Real**：可选轨迹对比并微调参数（默认关闭）"
    )


# 聊天与闭环进度（session 记忆）
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "flow_model_ok" not in st.session_state:
    st.session_state.flow_model_ok = False
if "flow_physics_ok" not in st.session_state:
    st.session_state.flow_physics_ok = False
if "flow_step_ok" not in st.session_state:
    st.session_state.flow_step_ok = False
if "last_run_diagnosis" not in st.session_state:
    st.session_state.last_run_diagnosis = None
if "last_proxy_summary" not in st.session_state:
    st.session_state.last_proxy_summary = None


def _init_engine() -> BaseEngine | None:
    try:
        if "engine" not in st.session_state:
            engine = create_engine()
            ref = st.session_state.get("model_ref", "default")
            engine.load(ref)
            engine.reset()
            st.session_state.engine = engine
            st.session_state.model_ref = ref
            st.session_state.flow_model_ok = True
            st.session_state.engine_error = ""
        return st.session_state.engine
    except Exception:
        st.session_state.engine_error = FRIENDLY_BLOCKED
        return None


def _safe_state(engine: BaseEngine) -> dict:
    try:
        return engine.get_state()
    except Exception:
        return {"t": 0, "joint_positions": [], "model_ref": "", "error": FRIENDLY_BLOCKED}


def _clear_widget_caches() -> None:
    for key in list(st.session_state.keys()):
        k = str(key)
        if k.startswith("joint_target_") or k.startswith("phys_"):
            del st.session_state[key]
    st.session_state.pop("last_physics", None)


def _load_model(engine: BaseEngine, ref: str) -> bool:
    """加载模型；失败时尝试回退默认臂。"""
    try:
        engine.load(ref)
        engine.reset()
        st.session_state.model_ref = ref
        _clear_widget_caches()
        st.session_state.flow_model_ok = True
        st.session_state.flow_physics_ok = False
        st.session_state.flow_step_ok = False
        return True
    except Exception:
        try:
            engine.load("default")
            engine.reset()
            st.session_state.model_ref = "default"
            _clear_widget_caches()
            st.session_state.flow_model_ok = True
            st.warning("模型加载失败，已回退到默认内置臂。")
        except Exception:
            st.session_state.flow_model_ok = False
            st.warning(FRIENDLY_BLOCKED)
        return False


engine = _init_engine()
if engine is None:
    st.warning(st.session_state.get("engine_error") or FRIENDLY_BLOCKED)
    st.stop()

# ---------- 能力边界与诊断（始终可见） ----------
_robot_preview = create_robot()
from config import settings as _settings_mod

_llm_effective = str(getattr(_settings_mod, "effective_llm_backend", lambda: setting("LLM_BACKEND", "mock"))())
_llm_note = str(getattr(_settings_mod, "llm_config_note", lambda: "")())
_status = build_system_status(
    llm_backend=_llm_effective,
    engine_backend=str(setting("ENGINE_BACKEND", "mujoco")),
    robot_backend=str(setting("ROBOT_BACKEND", "mock")),
    use_real_robot=bool(setting("USE_REAL_ROBOT", False)),
    use_rsr_config=bool(setting("USE_REAL_SIM_REAL", False)),
    rsr_ui=bool(st.session_state.get("rsr_enable_ui", False)),
    robot_name=str(getattr(_robot_preview, "name", "")),
    model_ref=str(st.session_state.get("model_ref", "default")),
    engine_ok=True,
    llm_config_note=_llm_note,
    robot_endpoint=str(setting("ROBOT_EXECUTE_ENDPOINT", "") or ""),
)
_banner = _status.get("real_robot_banner") or real_robot_safety_banner(
    use_real_robot=bool(setting("USE_REAL_ROBOT", False)),
    robot_backend=str(setting("ROBOT_BACKEND", "mock")),
    robot_name=str(getattr(_robot_preview, "name", "")),
    robot_endpoint=str(setting("ROBOT_EXECUTE_ENDPOINT", "") or ""),
)
# 真发开/关：顶栏强提示（关着说清楚不会动真机；开着必须醒目）
_banner_body = "**" + str(_banner.get("title") or "") + "**\n\n" + "\n\n".join(
    f"- {x}" for x in (_banner.get("lines") or [])
)
if _banner.get("level") == "danger":
    st.error(_banner_body)
elif _banner.get("level") == "warn":
    st.warning(_banner_body)
else:
    st.info(_banner_body)

with st.expander("能力边界与运行诊断（看这里就知道能不能行）", expanded=True):
    if _status.get("ready"):
        st.success("系统就绪：可以输入自然语言做虚拟试机。")
    else:
        st.error("系统未完全就绪，请先处理下方「需注意」。")

    # 步骤1：可选能力一览（默认关也要被看见）
    st.markdown(feature_catalog_markdown())

    # 步骤2：开闭状态条（关 / 已开成功 / 想开失败）
    _llm_want = str(setting("LLM_BACKEND", "mock") or "mock")
    _api_cfg = bool(getattr(_settings_mod, "llm_api_configured", lambda: False)())
    _switches = build_feature_switch_states(
        use_real_robot=bool(setting("USE_REAL_ROBOT", False)),
        robot_backend=str(setting("ROBOT_BACKEND", "mock")),
        robot_endpoint=str(setting("ROBOT_EXECUTE_ENDPOINT", "") or ""),
        robot_name=str(getattr(_robot_preview, "name", "")),
        llm_backend_wanted=_llm_want,
        llm_backend_effective=_llm_effective,
        llm_api_configured=_api_cfg,
        use_rsr_config=bool(setting("USE_REAL_SIM_REAL", False)),
        rsr_ui=bool(st.session_state.get("rsr_enable_ui", False)),
    )
    st.markdown("**开闭状态（是否开启成功）**")
    for _row in _switches:
        _line = format_feature_switch_line(_row)
        if _row.get("level") == "ok":
            st.success(_line)
        elif _row.get("level") == "warn":
            st.warning(_line)
        else:
            st.info(_line)

    st.markdown("**当前状态（正常项）**")
    for item in _status.get("ok_items") or []:
        st.markdown(f"- {item}")
    if _status.get("issues"):
        st.markdown("**需注意 / 常见误解**")
        for item in _status["issues"]:
            st.warning(item)
    st.markdown(capability_markdown(_llm_effective))
    st.caption(
        f"配置项 LLM_BACKEND={setting('LLM_BACKEND', 'mock')}　｜　"
        f"实际解析={_llm_effective}"
        + ("　｜　API 三项已配齐" if _llm_effective == "api" else "　｜　API 未启用或未配齐")
    )

    # HTTP 桥只读自检：不发任务单、不发抓取
    st.markdown("**真机桥自检（只读，不会发抓/放指令）**")
    st.caption(
        "点一下只检查「接收端网址能不能连上」。不会发送任务单，也不会让真臂做动作。"
        "假接收端需先另开窗口运行：python -m plugins.robot.local_fake_receiver"
    )
    if st.button("自检 HTTP 桥是否通", key="probe_http_bridge_btn"):
        from core.robot_bridge_probe import probe_http_bridge

        _probe = probe_http_bridge(timeout_sec=3.0)
        st.session_state.last_http_probe = _probe
    _probe_show = st.session_state.get("last_http_probe")
    if isinstance(_probe_show, dict) and _probe_show.get("message"):
        if _probe_show.get("ok"):
            st.success(_probe_show["message"])
        else:
            st.warning(_probe_show["message"])
        _ep = (_probe_show.get("endpoint_redacted") or {}).get("display") or "（未配置）"
        st.caption(f"探测地址摘要：{_ep}　｜　只读={_probe_show.get('read_only', True)}")

    # 云端 API 只读自检：不展示完整密钥；缺项可点直接提示
    st.markdown("**云端 API 自检（只读，不展示密钥原文）**")
    st.caption(
        "点一下检查「地址/密钥/模型是否通」。未配齐也会告诉你缺什么。"
        "演示默认用 mock，不必开 API；有额度时再测。"
    )
    if st.button("自检云端 API 是否通", key="probe_llm_api_btn"):
        from core.llm_api_probe import probe_llm_api

        st.session_state.last_llm_api_probe = probe_llm_api(timeout_sec=8.0)
    _api_probe = st.session_state.get("last_llm_api_probe")
    if isinstance(_api_probe, dict) and _api_probe.get("message"):
        if _api_probe.get("ok"):
            st.success(_api_probe["message"])
        else:
            st.warning(_api_probe["message"])
        _base_d = (_api_probe.get("base_redacted") or {}).get("display") or "（未配置）"
        _kh = _api_probe.get("key_hint") or "—"
        _md = _api_probe.get("model") or "—"
        st.caption(
            f"地址摘要：{_base_d}　｜　密钥：{_kh}　｜　模型：{_md}"
            f"　｜　只读={_api_probe.get('read_only', True)}"
        )

    # 接触试机入口（第13期）：一键切换场景 + 抓一次
    st.markdown("**接触试机（教学级，不是工业抓取）**")
    st.caption(
        "接触场景里，臂朝仿真方块的坐标伸过去——坐标来自模型，不是相机。"
        "碰到或近距推动 ≠ 抓住。默认臂没有物体，不会编造坐标。"
    )
    _c_hint = contact_scene_status_hint(st.session_state.get("model_ref", "default"))
    if _c_hint.get("level") == "ok":
        st.success(f"**{_c_hint['label']}** — {_c_hint['detail']}")
    else:
        st.info(f"**{_c_hint['label']}** — {_c_hint['detail']}")
    _cc1, _cc2 = st.columns(2)
    if _cc1.button(
        "切换到接触试机场景并抓一次",
        key="demo_contact_grab_btn",
        help="加载臂+方块场景，并自动填入「抓起红色积木」执行",
    ):
        if _load_model(engine, "builtin_arm2_contact"):
            st.session_state.pending_user_prompt = "抓起红色积木"
            st.rerun()
    if _cc2.button(
        "恢复默认臂（无物体）",
        key="demo_contact_default_btn",
        help="回到日常演示用的无物体内置臂",
    ):
        if _load_model(engine, "default"):
            st.success("已恢复默认内置臂（接触试机关）")
            st.rerun()

    st.markdown("**试一试样例（胡说 / 危险 / 正常 / 多步）**")
    st.caption(safety_demo_markdown())
    _samples = demo_instruction_samples()
    _scols = st.columns(len(_samples) + 1)
    for _i, _s in enumerate(_samples):
        if _scols[_i].button(_s["label"], key=f"demo_sample_{_s['id']}", help=_s.get("hint") or ""):
            st.session_state.pending_user_prompt = str(_s["text"])
            st.rerun()
    if _scols[-1].button("超限闸演示", key="demo_safety_overlimit", help="注入超大关节目标，看安全闸 clip/reject"):
        st.session_state.pending_overlimit_demo = True
        st.rerun()
    _last_diag = st.session_state.get("last_run_diagnosis")
    if isinstance(_last_diag, dict) and _last_diag.get("lines"):
        st.markdown("**最近一次执行诊断**")
        _lvl = _last_diag.get("level") or "info"
        _body = "\n".join(f"- {x}" for x in _last_diag["lines"])
        if _lvl == "success":
            st.success(_body)
        elif _lvl == "warning":
            st.warning(_body)
        else:
            st.error(_body)
    else:
        st.info("还没有执行过指令。发送一句后，这里会告诉你成功/失败原因与局限。")

    st.markdown("**本次试机代理摘要（一眼看用了哪些代理）**")
    st.caption("位姿不是相机；接触不是抓住；伪对照不是真回流。")
    _ps = st.session_state.get("last_proxy_summary")
    if isinstance(_ps, dict) and _ps:
        from core.pose_grounding_contract import format_proxy_summary_lines

        for _line in format_proxy_summary_lines(_ps):
            st.markdown(f"- {_line}")
    else:
        st.caption("还没跑过指令。跑一次后这里会列出：位姿来源 / 接触 / 是否多步 / RSR对照。")

# ---------- 自然语言编程（阶段 3） + RSR（阶段 6） ----------
st.subheader("自然语言编程")
_real_on = bool(setting("USE_REAL_ROBOT", False))
_rsr_cfg = bool(setting("USE_REAL_SIM_REAL", False))
_rsr_require = bool(setting("RSR_REQUIRE_REAL_TRAJECTORY", False))
st.caption(
    f"解析后端：{setting('LLM_BACKEND', 'mock')}　｜　"
    f"机器人：{setting('ROBOT_BACKEND', 'mock')}　｜　"
    f"真机发送：{'已开（可能动真臂）' if _real_on else '关（仅虚拟，真臂不动）'}　｜　"
    f"配置里 RSR 默认：{'开' if _rsr_cfg else '关'}　｜　"
    f"RSR 策略：{rsr_policy_label('require_real' if _rsr_require else 'prefer_real', require_real=_rsr_require)}"
)
if _real_on:
    st.caption("⚠ 真发已开：下方输入框发出的指令可能发到实验室。不确定就先改回 .env 关真发。")
else:
    st.caption("提示：真机与校准默认都关闭。每次执行后请看上方「最近一次执行诊断」。")

# 页面勾选可覆盖 .env；默认跟 USE_REAL_SIM_REAL（通常为关）
if "rsr_enable_ui" not in st.session_state:
    st.session_state.rsr_enable_ui = bool(setting("USE_REAL_SIM_REAL", False))
st.checkbox(
    "执行成功后做一次 Real-Sim-Real 校准（写回摩擦/阻尼；无真机时默认可用伪对照）",
    key="rsr_enable_ui",
    help=(
        "默认建议保持不勾选（关着=不会做校准）。"
        "勾选后：有合格真轨迹→真优先；没有→默认伪对照（会标明）。"
        "严模式见 .env 的 RSR_REQUIRE_REAL_TRAJECTORY。"
        "本机验真优先：python -m plugins.robot.local_fake_receiver --with-trajectory"
    ),
)
_rsr_hint = build_rsr_status_hint(
    rsr_enabled=bool(st.session_state.get("rsr_enable_ui", False)),
    last_rsr=st.session_state.get("last_rsr") if isinstance(st.session_state.get("last_rsr"), dict) else None,
    require_real_config=_rsr_require,
)
_rsr_line = format_rsr_status_line(_rsr_hint)
if _rsr_hint.get("level") == "ok":
    st.success(_rsr_line)
elif _rsr_hint.get("level") == "warn":
    st.warning(_rsr_line)
elif _rsr_hint.get("level") == "info":
    st.info(_rsr_line)
else:
    st.caption(_rsr_line.replace("**", ""))

for msg in st.session_state.chat_history:
    with st.chat_message(msg.get("role", "assistant")):
        st.write(msg.get("content", ""))
        if msg.get("meta"):
            with st.expander("详细数据（可选）", expanded=False):
                st.json(msg["meta"])

user_prompt = st.session_state.pop("pending_user_prompt", None)
if not user_prompt:
    user_prompt = st.chat_input("例如：抓起红色积木 / 先回零再抓红色杯子 / 回零")

# 超限闸演示：不改聊天输入习惯，单独注入超大 joint_targets
if st.session_state.pop("pending_overlimit_demo", None):
    from unittest.mock import patch

    st.session_state.chat_history.append(
        {
            "role": "user",
            "content": "【演示】抓起红色积木（故意超大关节目标）",
            "meta": None,
        }
    )
    try:
        pipeline = Pipeline(llm=create_llm(), engine=engine, robot=create_robot())
        huge = {"ok": True, "suggested_joint_targets": [9.0, -9.0]}
        with patch("core.pipeline.find_experience", return_value=huge):
            with patch("core.pipeline.mark_experience_used"):
                result = pipeline.run_instruction(
                    "抓起红色积木",
                    model_ref=st.session_state.get("model_ref", "default"),
                    real_sim_real=False,
                )
        gate = (result.data or {}).get("safety_gate") if isinstance(result.data, dict) else None
        diag = diagnose_run_result(
            ok=bool(result.ok),
            code=result.code,
            message=result.message,
            task_spec=((result.data or {}).get("task_spec") if isinstance(result.data, dict) else None),
            sim_result=((result.data or {}).get("sim_result") if isinstance(result.data, dict) else None),
            safety_gate=gate if isinstance(gate, dict) else None,
            experience_hit=True,
            llm_backend=str(setting("LLM_BACKEND", "mock")),
            use_real_robot=bool(setting("USE_REAL_ROBOT", False)),
        )
        st.session_state.last_run_diagnosis = diag
        if result.ok:
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": format_success_reply(
                        result.message,
                        action="grab",
                        target="red_block",
                        frame_count=len(((result.data or {}).get("sim_result") or {}).get("trajectory") or []),
                        experience_hit=True,
                        experiment_id=str(((result.data or {}).get("experiment") or {}).get("experiment_id") or ""),
                        robot_name="",
                        robot_msg="",
                        rsr_msg="未执行（演示）",
                        diagnosis=format_diagnosis_for_chat(diag),
                    ),
                    "meta": {
                        "demo": "overlimit",
                        "task_spec": (result.data or {}).get("task_spec"),
                        "safety_gate": gate,
                        "diagnosis": diag,
                    },
                }
            )
        else:
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": format_fail_reply(
                        result.message,
                        result.code,
                        diagnosis=format_diagnosis_for_chat(diag),
                    ),
                    "meta": {
                        "demo": "overlimit",
                        "code": result.code,
                        "safety_gate": gate,
                        "diagnosis": diag,
                    },
                }
            )
    except Exception:
        diag = diagnose_run_result(
            ok=False,
            code="INTERNAL",
            message=FRIENDLY_BLOCKED,
            llm_backend=str(setting("LLM_BACKEND", "mock")),
        )
        st.session_state.last_run_diagnosis = diag
        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "content": format_fail_reply(FRIENDLY_BLOCKED, "INTERNAL", diagnosis=format_diagnosis_for_chat(diag)),
                "meta": {"code": "INTERNAL", "diagnosis": diag},
            }
        )
    st.rerun()

if user_prompt:
    st.session_state.chat_history.append({"role": "user", "content": user_prompt, "meta": None})
    try:
        # 与页面共用同一引擎会话
        pipeline = Pipeline(llm=create_llm(), engine=engine, robot=create_robot())
        result = pipeline.run_instruction(
            user_prompt,
            model_ref=st.session_state.get("model_ref", "default"),
            real_sim_real=bool(st.session_state.get("rsr_enable_ui", False)),
        )
        if result.ok:
            spec = (result.data or {}).get("task_spec", {})
            sim = (result.data or {}).get("sim_result", {})
            exp_meta = (result.data or {}).get("experiment") or {}
            robot_meta = (result.data or {}).get("robot_result") or {}
            rsr_meta = (result.data or {}).get("rsr")
            hit = bool((result.data or {}).get("experience_hit"))
            adapters = (result.data or {}).get("adapters") or {}
            robot_msg = ""
            if isinstance(robot_meta, dict):
                robot_msg = str(robot_meta.get("message") or "")
            rsr_msg = format_rsr_run_message(
                rsr_meta if isinstance(rsr_meta, dict) else None,
                enabled=bool(st.session_state.get("rsr_enable_ui", False)),
            )
            from core.contact_scene_contract import format_contact_trial_message
            from core.multi_step_contract import format_multi_step_message
            from core.pose_grounding_contract import (
                build_proxy_summary,
                format_pose_grounding_message,
            )

            _sim_metrics = sim.get("metrics") if isinstance(sim.get("metrics"), dict) else {}
            _multi_meta = (result.data or {}).get("multi_step") if isinstance(result.data, dict) else None
            contact_msg = format_contact_trial_message(_sim_metrics)
            pose_msg = format_pose_grounding_message(_sim_metrics)
            multi_msg = format_multi_step_message(
                spec if isinstance(spec, dict) else {},
                _sim_metrics,
                _multi_meta if isinstance(_multi_meta, dict) else None,
            )
            diag = diagnose_run_result(
                ok=True,
                code=result.code,
                message=result.message,
                task_spec=spec if isinstance(spec, dict) else {},
                sim_result=sim if isinstance(sim, dict) else {},
                robot_result=robot_meta if isinstance(robot_meta, dict) else None,
                rsr=rsr_meta if isinstance(rsr_meta, dict) else None,
                safety_gate=((result.data or {}).get("safety_gate") if isinstance(result.data, dict) else None),
                experience_hit=hit,
                llm_backend=str(setting("LLM_BACKEND", "mock")),
                use_real_robot=bool(setting("USE_REAL_ROBOT", False)),
                multi_step=_multi_meta if isinstance(_multi_meta, dict) else None,
            )
            st.session_state.last_run_diagnosis = diag
            st.session_state.last_proxy_summary = build_proxy_summary(
                metrics=_sim_metrics,
                multi_step=_multi_meta if isinstance(_multi_meta, dict) else None,
                rsr=rsr_meta if isinstance(rsr_meta, dict) else None,
            )
            reply = format_success_reply(
                result.message,
                action=str(spec.get("action") or ""),
                target=str(spec.get("target") or ""),
                frame_count=len(sim.get("trajectory") or []),
                experience_hit=hit,
                experiment_id=str(exp_meta.get("experiment_id") or ""),
                robot_name=str(adapters.get("robot") or ""),
                robot_msg=robot_msg,
                rsr_msg=rsr_msg,
                contact_msg=contact_msg,
                multi_step_msg=multi_msg,
                pose_msg=pose_msg,
                diagnosis=format_diagnosis_for_chat(diag),
            )
            st.session_state.last_robot_result = robot_meta
            st.session_state.last_rsr = rsr_meta
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": reply,
                    "meta": {
                        "task_spec": spec,
                        "adapters": adapters,
                        "experience_hit": hit,
                        "experiment": exp_meta,
                        "robot_result": robot_meta,
                        "rsr": rsr_meta,
                        "diagnosis": diag,
                        "use_real_robot": setting("USE_REAL_ROBOT", False),
                        "use_real_sim_real": bool(st.session_state.get("rsr_enable_ui", False)),
                        "robot_backend": setting("ROBOT_BACKEND", "mock"),
                    },
                }
            )
            st.session_state.flow_step_ok = True
        else:
            diag = diagnose_run_result(
                ok=False,
                code=result.code,
                message=result.message,
                task_spec=((result.data or {}).get("task_spec") if isinstance(result.data, dict) else None),
                sim_result=((result.data or {}).get("sim_result") if isinstance(result.data, dict) else None),
                safety_gate=((result.data or {}).get("safety_gate") if isinstance(result.data, dict) else None),
                llm_backend=str(setting("LLM_BACKEND", "mock")),
                use_real_robot=bool(setting("USE_REAL_ROBOT", False)),
                multi_step=((result.data or {}).get("multi_step") if isinstance(result.data, dict) else None),
            )
            st.session_state.last_run_diagnosis = diag
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": format_fail_reply(
                        result.message,
                        result.code,
                        diagnosis=format_diagnosis_for_chat(diag),
                    ),
                    "meta": {
                        "code": result.code,
                        "experiment": (result.data or {}).get("experiment"),
                        "diagnosis": diag,
                    },
                }
            )
    except Exception:
        diag = diagnose_run_result(
            ok=False,
            code="INTERNAL",
            message=FRIENDLY_BLOCKED,
            llm_backend=str(setting("LLM_BACKEND", "mock")),
        )
        st.session_state.last_run_diagnosis = diag
        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "content": format_fail_reply(
                    FRIENDLY_BLOCKED,
                    "INTERNAL",
                    diagnosis=format_diagnosis_for_chat(diag),
                ),
                "meta": {"code": "INTERNAL", "diagnosis": diag},
            }
        )
    st.rerun()

if st.button("清空聊天记录"):
    st.session_state.chat_history = []
    st.rerun()

st.divider()
st.subheader("Real-Sim-Real 校准摘要")
st.caption(
    "关着=不会做校准。勾选上方开关并成功执行后这里才有内容；"
    "对照会标明「伪对照」或「真轨迹」。本机验真优先可用假接收端 --with-trajectory。"
)
_last_rsr = st.session_state.get("last_rsr")
_rsr_sum_hint = build_rsr_status_hint(
    rsr_enabled=bool(st.session_state.get("rsr_enable_ui", False)),
    last_rsr=_last_rsr if isinstance(_last_rsr, dict) else None,
    require_real_config=bool(setting("RSR_REQUIRE_REAL_TRAJECTORY", False)),
)
_sum_line = format_rsr_status_line(_rsr_sum_hint)
if _rsr_sum_hint.get("level") == "ok":
    st.success(_sum_line)
elif _rsr_sum_hint.get("level") == "warn":
    st.warning(_sum_line)
elif _rsr_sum_hint.get("level") == "info":
    st.info(_sum_line)
else:
    st.info(_sum_line)
if isinstance(_last_rsr, dict) and _last_rsr:
    _dev = _last_rsr.get("deviation") or {}
    _cal = _last_rsr.get("calibration") or {}
    _src_raw = _last_rsr.get("reference_source")
    _src_label = (
        rsr_reference_source_label(_src_raw)
        if _src_raw
        else ("跳过" if _last_rsr.get("skipped") else "—")
    )
    _pol_label = rsr_policy_label(
        _last_rsr.get("policy"),
        require_real=bool(_last_rsr.get("require_real_trajectory"))
        if "require_real_trajectory" in _last_rsr
        else None,
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("对照来源", _src_label)
    c2.metric("轨迹 MAE", f"{float(_dev.get('mae') or 0):.4f}" if _dev.get("mae") is not None else "—")
    c3.metric("参数已更新", "是" if _cal.get("updated") else "否")
    c4.metric(
        "对照帧数",
        str(_last_rsr.get("reference_frame_count") if _last_rsr.get("reference_frame_count") is not None else "—"),
    )
    st.caption(f"策略：{_pol_label}")
    st.write(
        {
            "message": _last_rsr.get("message"),
            "policy": _last_rsr.get("policy"),
            "reference_source": _src_raw,
            "reference_kind": _src_label,
            "reference_frame_count": _last_rsr.get("reference_frame_count"),
            "extract_reason": _last_rsr.get("extract_reason"),
            "before": _cal.get("before"),
            "after": _cal.get("after"),
            "deviation": {
                "mae": _dev.get("mae"),
                "rmse": _dev.get("rmse"),
                "max_abs": _dev.get("max_abs"),
            },
        }
    )
    try:
        st.caption("当前引擎物理参数（校准后可读）：")
        st.write(engine.list_physics_params())
    except Exception:
        st.caption("当前引擎暂无法读取物理参数。")
elif bool(st.session_state.get("rsr_enable_ui", False)):
    st.caption("已勾选校准，但还没有成功跑过带 RSR 的指令。发一句「抓起红色积木」后再看这里。")
else:
    st.caption("当前关着：不会做校准。需要时再勾选上方开关。")

st.divider()
st.subheader("实验数据与经验库")
st.caption("只读浏览本地已落盘记录；存储目录与格式未改，旧 JSON 仍可打开。")
c_exp, c_mem = st.columns(2)
with c_exp:
    st.markdown("**最近实验**")
    exp_rows = experiments_table_rows(8)
    if exp_rows:
        st.dataframe(exp_rows, width="stretch", hide_index=True)
    else:
        st.caption("暂无实验。发送一条自然语言指令后会出现在这里。")
    st.markdown("**导出一次演示包**")
    st.caption("打包：任务单 + 轨迹摘要 + 运行快照 + 说明（不含 API Key），便于答辩拷贝。")
    _pack_id = st.text_input("实验编号（可空=导出最近一条）", value="", key="demo_pack_exp_id")
    _c_pack1, _c_pack2 = st.columns(2)
    _do_latest = _c_pack1.button("导出最近一次", key="btn_demo_pack_latest")
    _do_id = _c_pack2.button("按编号导出", key="btn_demo_pack_id")
    if _do_latest or _do_id:
        from core.demo_pack import export_demo_pack

        _pack = export_demo_pack(
            (_pack_id.strip() if _do_id and _pack_id.strip() else None),
            latest=bool(_do_latest) or not (_pack_id or "").strip(),
        )
        if _pack.get("ok"):
            st.success(_pack.get("message") or "已导出")
            _zp = Path(str(_pack.get("zip_path") or ""))
            if _zp.is_file():
                st.download_button(
                    label="下载演示包 zip",
                    data=_zp.read_bytes(),
                    file_name=_zp.name,
                    mime="application/zip",
                    key=f"dl_demo_pack_{_pack.get('experiment_id')}",
                )
                st.caption(f"本机路径：{_zp}")
        else:
            st.warning(_pack.get("message") or "导出失败")

with c_mem:
    st.markdown("**经验条目**")
    mem_rows = experiences_table_rows(8)
    if mem_rows:
        st.dataframe(mem_rows, width="stretch", hide_index=True)
    else:
        st.caption("暂无经验。成功执行后会写入可复用条目。")
with st.expander("原始摘要（调试）", expanded=False):
    st.write({"experiments": list_recent_experiments(5), "experience": list_experiences(5)})
st.caption(f"目录：{settings.EXPERIMENTS_DIR} ｜ {settings.EXPERIENCE_DIR}")

st.divider()

# 进度条
m1, m2, m3 = st.columns(3)
m1.metric("① 模型", "完成" if st.session_state.flow_model_ok else "待做")
m2.metric("② 物理参数", "完成" if st.session_state.flow_physics_ok else "待做")
m3.metric("③ 关节/语言执行", "完成" if st.session_state.flow_step_ok else "待做")

# ---------- ① 模型 ----------
st.subheader("① 模型选择与导入")
options = list_model_options()
labels = [o["label"] for o in options]
refs = [o["ref"] for o in options]
current_ref = st.session_state.get("model_ref", "default")
try:
    current_index = refs.index(current_ref)
except ValueError:
    current_index = 0

selected_label = st.selectbox("可用模型", labels, index=current_index)
selected_ref = refs[labels.index(selected_label)]

up = st.file_uploader("上传 MJCF 模型（.xml / .mjcf）", type=["xml", "mjcf"])
c_load, c_default = st.columns(2)
with c_load:
    do_load = st.button("加载所选模型", type="primary", use_container_width=True)
with c_default:
    do_default = st.button("恢复默认内置臂", use_container_width=True)

if up is not None and st.button("保存上传文件", use_container_width=True):
    result = save_uploaded_model(up.name, up.getvalue())
    if result.get("ok") == "true":
        st.success(result.get("message", "上传成功"))
        st.session_state.pending_upload_ref = result.get("ref", "")
        st.rerun()
    else:
        st.warning(result.get("message") or FRIENDLY_BLOCKED)

if st.session_state.get("pending_upload_ref"):
    pending = st.session_state.pop("pending_upload_ref")
    if _load_model(engine, pending):
        st.success(f"已加载上传模型：{pending}")
        st.rerun()

if do_default:
    if _load_model(engine, "default"):
        st.success("已恢复默认内置臂")
        st.rerun()

if do_load:
    if _load_model(engine, selected_ref):
        st.success(f"已加载：{selected_ref}")
        st.rerun()

# ---------- ② 物理参数 ----------
st.divider()
st.subheader("② 物理参数（白名单）")
try:
    phys = engine.list_physics_params()
except Exception:
    phys = {}
    st.warning(FRIENDLY_BLOCKED)

if "phys_friction" not in st.session_state:
    st.session_state.phys_friction = float(phys.get("friction", 1.0))
if "phys_damping" not in st.session_state:
    st.session_state.phys_damping = float(phys.get("joint_damping", 0.5))
if "phys_rmin" not in st.session_state:
    st.session_state.phys_rmin = float(phys.get("joint_range_min", -2.8))
if "phys_rmax" not in st.session_state:
    st.session_state.phys_rmax = float(phys.get("joint_range_max", 2.8))

p1, p2 = st.columns(2)
with p1:
    st.slider("摩擦系数 friction", 0.0, 2.0, step=0.05, key="phys_friction")
    st.slider("关节阻尼 joint_damping", 0.0, 5.0, step=0.05, key="phys_damping")
with p2:
    st.slider("关节限位下限", -3.14, 3.14, step=0.05, key="phys_rmin")
    st.slider("关节限位上限", -3.14, 3.14, step=0.05, key="phys_rmax")

if st.button("应用物理参数", type="primary", use_container_width=True):
    try:
        applied = engine.set_physics_params(
            {
                "friction": float(st.session_state.phys_friction),
                "joint_damping": float(st.session_state.phys_damping),
                "joint_range_min": float(st.session_state.phys_rmin),
                "joint_range_max": float(st.session_state.phys_rmax),
            }
        )
        st.session_state.last_physics = applied
        st.session_state.flow_physics_ok = True
        st.success("物理参数已写入引擎")
    except Exception:
        st.warning(FRIENDLY_BLOCKED)

if st.session_state.get("last_physics"):
    st.caption("最近一次写入快照：")
    st.write(st.session_state.last_physics)
else:
    st.caption("当前引擎读取到的参数：")
    st.write(
        {
            k: phys.get(k)
            for k in ("friction", "joint_damping", "joint_range_min", "joint_range_max")
            if k in phys
        }
    )

# ---------- ③ 关节步进 ----------
state = _safe_state(engine)
joints = list(state.get("joint_positions") or [])
n_joints = len(joints) if joints else 2
n_joints = max(1, min(n_joints, 8))

# 关节滑条范围尽量跟随已应用的限位
jmin = float(st.session_state.get("phys_rmin", -2.8))
jmax = float(st.session_state.get("phys_rmax", 2.8))
if jmin > jmax:
    jmin, jmax = jmax, jmin

for i in range(n_joints):
    key = f"joint_target_{i}"
    if key not in st.session_state:
        st.session_state[key] = float(joints[i]) if i < len(joints) else 0.0
    # 夹紧到当前限位，避免超出 slider 范围报错
    st.session_state[key] = min(jmax, max(jmin, float(st.session_state[key])))

st.divider()
st.subheader("③ 关节目标与步进")
cols = st.columns(min(n_joints, 4))
targets: list[float] = []
for i in range(n_joints):
    with cols[i % len(cols)]:
        val = st.slider(
            f"关节 {i + 1}",
            min_value=jmin,
            max_value=jmax,
            step=0.05,
            key=f"joint_target_{i}",
        )
        targets.append(float(val))

c1, c2, c3 = st.columns(3)
with c1:
    do_step = st.button("应用并步进", type="primary", use_container_width=True)
with c2:
    do_reset = st.button("重置仿真", use_container_width=True)
with c3:
    do_reload = st.button("重新加载当前模型", use_container_width=True)

try:
    if do_reload:
        _load_model(engine, st.session_state.get("model_ref", "default"))
        st.success("当前模型已重新加载")
        st.rerun()
    elif do_reset:
        engine.reset()
        st.session_state.flow_step_ok = False
        st.success("已重置到初始状态")
    elif do_step:
        state = engine.step({"action": "move", "joint_targets": targets, "nsub": 40})
        st.session_state.flow_step_ok = True
        st.success("已完成一步仿真")
    else:
        state = _safe_state(engine)
except Exception:
    st.warning(FRIENDLY_BLOCKED)
    state = _safe_state(engine)

st.divider()
st.subheader("当前仿真状态")
jp = list(state.get("joint_positions") or [])
st.metric("仿真步序号 t", value=int(state.get("t") or 0))
st.write(
    {
        "joint_positions": jp,
        "model_ref": state.get("model_ref") or st.session_state.get("model_ref", ""),
        "flow": {
            "model": st.session_state.flow_model_ok,
            "physics": st.session_state.flow_physics_ok,
            "step": st.session_state.flow_step_ok,
        },
    }
)

if (
    st.session_state.flow_model_ok
    and st.session_state.flow_physics_ok
    and st.session_state.flow_step_ok
):
    st.success("整站闭环已跑通：模型 + 物理参数 + 关节步进。")

with st.expander("运行配置"):
    st.write(
        {
            "engine_backend": setting("ENGINE_BACKEND", "mujoco"),
            "llm_backend": setting("LLM_BACKEND", "mock"),
            "robot_backend": setting("ROBOT_BACKEND", "mock"),
            "use_real_robot": setting("USE_REAL_ROBOT", False),
            "use_real_sim_real": setting("USE_REAL_SIM_REAL", False),
            "rsr_enable_ui": bool(st.session_state.get("rsr_enable_ui", False)),
            "rsr_calib_gain": setting("RSR_CALIB_GAIN", 0.5),
            "robot_name": create_robot().name,
            "robot_endpoint": setting("ROBOT_EXECUTE_ENDPOINT", "") or "（未配置）",
            "engine_name": getattr(engine, "name", ""),
            "session_model_ref": st.session_state.get("model_ref", ""),
            "last_robot_result": st.session_state.get("last_robot_result"),
            "last_rsr": st.session_state.get("last_rsr"),
            "chat_turns": len(st.session_state.get("chat_history", [])),
            "local_url": f"http://{setting('APP_HOST', '127.0.0.1')}:{setting('APP_PORT', 8501)}",
        }
    )
