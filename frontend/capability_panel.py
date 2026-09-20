# -*- coding: utf-8 -*-
"""
能力边界与运行诊断（给零基础用户看：能做什么、哪里可能出问题）。
与 Streamlit 解耦，便于单测。
"""

from __future__ import annotations

from typing import Any


def feature_catalog_items() -> list[dict[str, str]]:
    """
    可选能力清单（步骤1：默认关也要被看见）。
    只描述「有什么 / 默认关 / 怎么开」，不含开闭成功判定（留给步骤2）。
    """
    return [
        {
            "id": "real_robot",
            "title": "真机发送",
            "what": "把同一张任务单发给实验室接收端（或本机假接收端），可能让真臂动起来。",
            "default": "默认关闭（安全）——平时只跑电脑里的虚拟臂。",
            "how": (
                "要打开时：用记事本改项目里的 .env，设 USE_REAL_ROBOT=true，"
                "再设 ROBOT_BACKEND=http 与 ROBOT_EXECUTE_ENDPOINT=接收端网址，然后重启网站。"
                "细节见 plugins/robot/真机联调检查清单.txt"
            ),
        },
        {
            "id": "rsr",
            "title": "RSR 虚实校准",
            "what": "用对照轨迹微调仿真参数（摩擦/阻尼等）。没有真机轨迹时，可能用「假对照」做软件演示。",
            "default": "默认关闭——不勾选、不改配置时不会做校准。",
            "how": (
                "临时试用：在下方勾选「执行成功后做一次 Real-Sim-Real 校准」。"
                "长期默认开：在 .env 设 USE_REAL_SIM_REAL=true 后重启。"
                "有真机轨迹会优先用真轨迹；没有则默认可用伪对照（会标明）。"
                "本机可验真优先：假接收端加 --with-trajectory。"
                "实验室严模式（少用）：.env 设 RSR_REQUIRE_REAL_TRAJECTORY=true（无真轨迹则跳过校准）。"
            ),
        },
        {
            "id": "cloud_api",
            "title": "云端语言 API",
            "what": "用云端大模型（如 Kimi/Moonshot）把更自然的中文解析成任务单；未开时用本地关键词 mock。",
            "default": "默认关闭（mock）——免额度、演示稳定。",
            "how": (
                "要打开时：在 .env 填写 LLM_API_BASE、LLM_API_KEY、LLM_MODEL_NAME，"
                "再设 LLM_BACKEND=api，然后重启网站。"
                "若密钥无效或余额不足，会自动回退 mock，网站不崩。"
            ),
        },
        {
            "id": "contact_trial",
            "title": "接触试机",
            "what": (
                "在带方块的场景里：臂朝仿真里的方块坐标伸过去（不是相机看到的），"
                "再看末端有没有碰到/接近（教学级 grasp_proxy）。"
                "不是工业夹爪，也不代表现实已抓住。"
            ),
            "default": "默认关闭——平时用无物体的内置臂，只做关节示意（不编造物体坐标）。",
            "how": (
                "打开方式：在能力区点「切换到接触试机场景并抓一次」，"
                "或到「① 模型」选择「接触试机场景（臂+方块）」。"
                "跑完后看诊断里的「场景位姿示意」「接触试机」，以及能力区「本次试机代理摘要」。"
                "演示结束可点「恢复默认臂」。"
            ),
        },
        {
            "id": "multi_step",
            "title": "多步试机",
            "what": (
                "一句指令可含「先…再…」等有序子动作（如先回零再抓），"
                "按顺序在仿真里执行；失败会标明第几步。"
            ),
            "default": "默认可用——直接说多步句子即可；也可点样例按钮。",
            "how": (
                "例句：先回零再抓红色杯子；或点「多步样例」。"
                "看诊断里的「多步试机」一行。"
                "注意：params 里的 steps 是单次仿真细分，和多步编排不是一回事。"
            ),
        },
    ]


def feature_catalog_markdown() -> str:
    """能力清单一眼可见的 Markdown（关着也能看见有这些功能）。"""
    lines = [
        "### 可选能力一览（默认都关着，但功能在）",
        "下面几项**就算现在关着，也算本产品具备的能力**；打开前请先看「怎么开」。",
        "",
    ]
    for i, item in enumerate(feature_catalog_items(), start=1):
        lines.append(f"**{i}. {item['title']}**")
        lines.append(f"- 是什么：{item['what']}")
        lines.append(f"- {item['default']}")
        lines.append(f"- 怎么开：{item['how']}")
        lines.append("")
    lines.append(
        "下面还有「开闭状态」：告诉你真机 / RSR / API 现在是关着、已开成功，还是想开但没成功。"
        "接触试机看当前加载的模型；多步试机直接说「先…再…」即可。"
    )
    return "\n".join(lines).strip()


def contact_scene_status_hint(model_ref: str | None) -> dict[str, str]:
    """接触试机开闭提示（由当前 model_ref 决定，不读 .env）。"""
    from core.contact_scene_contract import is_contact_scene_model_ref

    if is_contact_scene_model_ref(model_ref):
        return {
            "level": "ok",
            "label": "接触试机：已开（接触场景）",
            "detail": (
                "当前模型含试机方块。发「抓」后臂会朝仿真里的方块位置示意（不是相机），"
                "并看诊断里的接触试机结果。代理通过≠工业夹稳≠现实抓住。"
            ),
        }
    return {
        "level": "safe",
        "label": "接触试机：关（默认臂，无物体）",
        "detail": (
            "当前只是关节示意，没有用场景物体坐标（本产品没有相机）。"
            "要点「切换到接触试机场景并抓一次」，或在①模型里选接触试机场景。"
        ),
    }


def build_feature_switch_states(
    *,
    use_real_robot: bool,
    robot_backend: str = "mock",
    robot_endpoint: str = "",
    robot_name: str = "",
    llm_backend_wanted: str = "mock",
    llm_backend_effective: str = "mock",
    llm_api_configured: bool = False,
    use_rsr_config: bool = False,
    rsr_ui: bool = False,
) -> list[dict[str, Any]]:
    """
    三项可选能力的开闭状态（步骤2）。
    state: off=关（安全） / ready=已开且就绪 / failed=想开但未成功
    level: safe | ok | warn（给网站配色用）
    """
    backend = (robot_backend or "mock").strip().lower()
    rname = (robot_name or "").strip().lower()
    ep = str(robot_endpoint or "").strip()
    want_llm = (llm_backend_wanted or "mock").strip().lower()
    eff_llm = (llm_backend_effective or "mock").strip().lower()

    # —— 真机 ——
    if not use_real_robot:
        robot_row = {
            "id": "real_robot",
            "title": "真机发送",
            "state": "off",
            "level": "safe",
            "label": "关（安全）",
            "reason": "真实机械臂不会动；只在虚拟臂上演示。",
        }
    elif rname in {"http_robot", "ros_robot"}:
        robot_row = {
            "id": "real_robot",
            "title": "真机发送",
            "state": "ready",
            "level": "ok",
            "label": "已开且就绪",
            "reason": f"当前通道={robot_name or backend}。说指令可能发到接收端，请注意安全。",
        }
    else:
        # 开关开了但仍是 mock：缺后端或地址/Domain
        if backend == "mock":
            why = "USE_REAL_ROBOT=true，但 ROBOT_BACKEND 仍是 mock，没有真正外发。"
        elif backend == "http" and not ep:
            why = "已开真发且选了 http，但未填写 ROBOT_EXECUTE_ENDPOINT（接收端网址）。"
        elif backend in {"ros", "ros2"}:
            why = "已开真发且选了 ros，但本机可能缺 rclpy 或 Domain 未配齐，已回退虚拟臂。"
        else:
            why = "已开真发，但当前仍回退到虚拟臂；请检查 ROBOT_BACKEND 与地址/Domain。"
        robot_row = {
            "id": "real_robot",
            "title": "真机发送",
            "state": "failed",
            "level": "warn",
            "label": "想开但未成功",
            "reason": why,
        }

    # —— 云端 API ——
    want_api = want_llm in {"api", "cloud", "openai"}
    if not want_api:
        api_row = {
            "id": "cloud_api",
            "title": "云端语言 API",
            "state": "off",
            "level": "safe",
            "label": "关（安全）",
            "reason": "当前用本地 mock 解析（免额度）。",
        }
    elif eff_llm == "api" and llm_api_configured:
        api_row = {
            "id": "cloud_api",
            "title": "云端语言 API",
            "state": "ready",
            "level": "ok",
            "label": "已开且就绪",
            "reason": "已按 api 解析；网络或额度问题会导致单次失败，不会把网站打崩。",
        }
    else:
        missing = []
        if not llm_api_configured:
            # 不读出密钥内容，只说缺哪类
            try:
                from config.safe import setting

                if not str(setting("LLM_API_BASE", "") or "").strip():
                    missing.append("地址 LLM_API_BASE")
                if not str(setting("LLM_API_KEY", "") or "").strip():
                    missing.append("密钥 LLM_API_KEY")
                if not str(setting("LLM_MODEL_NAME", "") or "").strip():
                    missing.append("模型名 LLM_MODEL_NAME")
            except Exception:
                missing.append("API 地址/密钥/模型名")
        why = "已设 LLM_BACKEND=api，但未配齐，已自动回退 mock。"
        if missing:
            why = "已设要开 api，但还缺：" + "、".join(missing) + "。已回退 mock，网站可继续用。"
        api_row = {
            "id": "cloud_api",
            "title": "云端语言 API",
            "state": "failed",
            "level": "warn",
            "label": "想开但未成功",
            "reason": why,
        }

    # —— RSR ——
    rsr_on = bool(use_rsr_config or rsr_ui)
    if not rsr_on:
        rsr_row = {
            "id": "rsr",
            "title": "RSR 虚实校准",
            "state": "off",
            "level": "safe",
            "label": "关（安全）",
            "reason": "不会做校准；页面勾选或 .env 打开后才会在成功执行后校准。",
        }
    else:
        src_bits = []
        if rsr_ui:
            src_bits.append("页面已勾选")
        if use_rsr_config:
            src_bits.append(".env 已开 USE_REAL_SIM_REAL")
        rsr_row = {
            "id": "rsr",
            "title": "RSR 虚实校准",
            "state": "ready",
            "level": "ok",
            "label": "已开且就绪",
            "reason": (
                "、".join(src_bits) + "。"
                "下次成功执行后会尝试校准；无真机轨迹时可能用假对照（步骤4会写得更细）。"
            ),
        }

    # 固定顺序与清单一致：真机、RSR、API
    return [robot_row, rsr_row, api_row]


def format_feature_switch_line(row: dict[str, Any]) -> str:
    """单行人话：标题：状态 — 原因。"""
    title = str(row.get("title") or "")
    label = str(row.get("label") or "")
    reason = str(row.get("reason") or "")
    return f"**{title}：{label}** — {reason}"


def rsr_reference_source_label(source: str | None) -> str:
    """
    对照来源代码 → 零基础人话。
    保留代码名映射，不把伪对照写成终局（第12期真轨迹优先仍可替换）。
    """
    src = str(source or "").strip().lower()
    if src in {"robot", "real", "real_robot", "true"}:
        return "真轨迹"
    if src in {"pseudo_real", "pseudo", "synthetic"}:
        return "伪对照"
    if not src:
        return "（未知对照）"
    return f"其它（{src}）"


def rsr_policy_label(policy: str | None, *, require_real: bool | None = None) -> str:
    """策略代码 → 人话。"""
    p = str(policy or "").strip().lower()
    if require_real is True or p in {"require_real", "require", "strict"}:
        return "严模式（无真轨迹则跳过）"
    if p in {"prefer_real", "prefer", ""} or require_real is False:
        return "默认（真优先，无则伪对照）"
    return f"其它策略（{p}）"


def format_rsr_run_message(rsr: dict[str, Any] | None, *, enabled: bool) -> str:
    """聊天/摘要用的一句 RSR 结果（含对照类型、策略、帧数）。"""
    if not enabled and not isinstance(rsr, dict):
        return "未执行（关着，不会做校准）"
    if not isinstance(rsr, dict):
        return "未执行（已开但本次无校准结果）"
    policy_txt = rsr_policy_label(
        rsr.get("policy"),
        require_real=bool(rsr.get("require_real_trajectory"))
        if "require_real_trajectory" in rsr
        else None,
    )
    if rsr.get("skipped"):
        reason = str(rsr.get("message") or rsr.get("extract_reason") or "无对照轨迹")
        # 坏轨迹：提取看到过但不合格
        if rsr.get("extract_reason") and "未找到" not in str(rsr.get("extract_reason")):
            reason = f"{reason}；轨迹形状：{rsr.get('extract_reason')}"
        return f"已跳过（{reason}｜策略={policy_txt}）"
    if rsr.get("ok"):
        mae = ((rsr.get("deviation") or {}).get("mae"))
        mae_txt = f"{float(mae):.4f}" if mae is not None else "—"
        kind = rsr_reference_source_label(rsr.get("reference_source"))
        n = rsr.get("reference_frame_count")
        n_txt = f"，帧数={int(n)}" if n is not None else ""
        return f"已完成（对照={kind}{n_txt}，偏差 MAE={mae_txt}｜策略={policy_txt}）"
    return str(rsr.get("message") or "未成功")


def build_rsr_status_hint(
    *,
    rsr_enabled: bool,
    last_rsr: dict[str, Any] | None = None,
    require_real_config: bool = False,
) -> dict[str, Any]:
    """
    RSR 状态提示：关着写清不会校准；开着区分未执行 / 伪对照 / 真轨迹 / 严模式跳过。

    mode: off | waiting | pseudo | real | skipped | failed
    level: safe | info | ok | warn
    """
    if not rsr_enabled:
        return {
            "mode": "off",
            "level": "safe",
            "label": "关 — 不会做校准",
            "detail": (
                "未勾选且配置未开时，即使指令执行成功，也不会做虚实校准。"
                "需要时再勾选下方开关（或 .env 设 USE_REAL_SIM_REAL=true）。"
            ),
            "reference_kind": "",
            "policy_label": "",
        }

    cfg_policy = rsr_policy_label(
        "require_real" if require_real_config else "prefer_real",
        require_real=require_real_config,
    )

    if not isinstance(last_rsr, dict) or not last_rsr:
        detail = (
            "下次成功执行后才会校准。"
            "有真机轨迹时用真轨迹；没有时默认可用伪对照（会标明，不是真机回流）。"
        )
        if require_real_config:
            detail = (
                "当前为严模式：没有合格真轨迹将跳过校准（不会用伪对照）。"
                "本机演示真优先可用：假接收端加 --with-trajectory。"
            )
        return {
            "mode": "waiting",
            "level": "info",
            "label": "已开 · 尚未执行",
            "detail": detail + f" 当前策略：{cfg_policy}。",
            "reference_kind": "",
            "policy_label": cfg_policy,
        }

    last_policy = rsr_policy_label(
        last_rsr.get("policy"),
        require_real=bool(last_rsr.get("require_real_trajectory"))
        if "require_real_trajectory" in last_rsr
        else require_real_config,
    )

    if last_rsr.get("skipped"):
        detail = str(last_rsr.get("message") or "无对照轨迹，未做校准。")
        er = str(last_rsr.get("extract_reason") or "").strip()
        if er and "未找到" not in er:
            detail = f"{detail}（轨迹不合格：{er}）"
        detail = detail + f" 策略：{last_policy}。"
        return {
            "mode": "skipped",
            "level": "warn",
            "label": "最近一次 · 已跳过",
            "detail": detail,
            "reference_kind": "",
            "policy_label": last_policy,
        }

    src = str(last_rsr.get("reference_source") or "").strip().lower()
    kind = rsr_reference_source_label(src)
    n = last_rsr.get("reference_frame_count")
    n_bit = f"对照帧数 {int(n)}。" if n is not None else ""

    if last_rsr.get("ok"):
        if src in {"pseudo_real", "pseudo", "synthetic"}:
            return {
                "mode": "pseudo",
                "level": "ok",
                "label": "最近一次 · 伪对照",
                "detail": (
                    "用的是软件假对照轨迹，方便本机演示链路；不是真机回流。"
                    f"{n_bit}有合格真轨迹时会优先用真轨迹。策略：{last_policy}。"
                ),
                "reference_kind": kind,
                "policy_label": last_policy,
            }
        if src in {"robot", "real", "real_robot", "true"}:
            return {
                "mode": "real",
                "level": "ok",
                "label": "最近一次 · 真轨迹",
                "detail": (
                    "对照来自接收端回传的轨迹（真机或带 --with-trajectory 的假接收端）。"
                    f"{n_bit}策略：{last_policy}。"
                ),
                "reference_kind": kind,
                "policy_label": last_policy,
            }
        return {
            "mode": "pseudo" if "pseudo" in src else "real",
            "level": "ok",
            "label": f"最近一次 · {kind}",
            "detail": str(last_rsr.get("message") or "校准已完成。") + f" 策略：{last_policy}。",
            "reference_kind": kind,
            "policy_label": last_policy,
        }

    return {
        "mode": "failed",
        "level": "warn",
        "label": "最近一次 · 未成功",
        "detail": str(last_rsr.get("message") or "校准未成功，详见下方摘要。")
        + f" 策略：{last_policy}。",
        "reference_kind": kind if src else "",
        "policy_label": last_policy,
    }


def format_rsr_status_line(hint: dict[str, Any]) -> str:
    """单行展示：标签 — 说明。"""
    label = str(hint.get("label") or "")
    detail = str(hint.get("detail") or "")
    return f"**RSR：{label}** — {detail}"


def real_robot_safety_banner(
    *,
    use_real_robot: bool,
    robot_backend: str = "mock",
    robot_name: str = "",
    robot_endpoint: str = "",
) -> dict[str, Any]:
    """
    真发开/关的人话横幅（给网站顶栏/能力区用）。
    level: safe | danger | warn
    """
    from core.robot_bridge_contract import redact_robot_endpoint

    backend = (robot_backend or "mock").strip().lower()
    name = (robot_name or backend or "mock").strip()
    red = redact_robot_endpoint(robot_endpoint)
    display = str(red.get("display") or "") or "（未填写接收端网址）"

    if not use_real_robot:
        return {
            "level": "safe",
            "title": "真机发送：关（安全）",
            "lines": [
                "现在不会把指令发到真机械臂，只在电脑里的虚拟臂上演示。",
                "若要真连实验室：改 .env 打开 USE_REAL_ROBOT，并按「真机联调检查清单」操作。",
            ],
            "endpoint_display": display,
            "use_real_robot": False,
            "robot_backend": backend,
            "robot_name": name,
        }

    lines = [
        "真机发送已打开：你在网站说的指令，可能会发到实验室接收端（真臂可能运动）。",
        "请确认：周围无人伸手、急停可用、实验室同事知情。",
        f"当前通道：{name}（配置 ROBOT_BACKEND={backend}）",
        f"接收端地址摘要：{display}",
        "演示结束后请改回 USE_REAL_ROBOT=false、ROBOT_BACKEND=mock，并重启网站。",
    ]
    level = "danger"
    if backend == "mock":
        level = "warn"
        lines.insert(
            1,
            "注意：开关开着，但后端仍是 mock（虚拟臂）— 真臂通常还不会动；请核对配置是否写错。",
        )
    return {
        "level": level,
        "title": "真机发送：已开（请小心）" if level == "danger" else "真机发送：开着但可能未真正外发",
        "lines": lines,
        "endpoint_display": display,
        "use_real_robot": True,
        "robot_backend": backend,
        "robot_name": name,
    }


def build_system_status(
    *,
    llm_backend: str,
    engine_backend: str,
    robot_backend: str,
    use_real_robot: bool,
    use_rsr_config: bool,
    rsr_ui: bool,
    robot_name: str,
    model_ref: str,
    engine_ok: bool,
    llm_config_note: str = "",
    robot_endpoint: str = "",
) -> dict[str, Any]:
    """汇总当前运行配置与是否就绪。"""
    llm = (llm_backend or "mock").strip().lower()
    issues: list[str] = []
    ok_items: list[str] = []

    if engine_ok:
        ok_items.append(f"仿真引擎已加载（{engine_backend}，模型={model_ref or 'default'}）")
    else:
        issues.append("仿真引擎未就绪：请检查 MuJoCo/模型文件，或重启网站")

    if llm == "api":
        ok_items.append("语言解析：api（真大模型，说法更自由）")
    else:
        ok_items.append("语言解析：mock（本地关键词，免密钥）")
        # 仅当「本来就想用 mock」时提示能力边界；若是 api 回退，用下面的 note
        if not (llm_config_note or "").strip():
            issues.append(
                "未开 API 时，只能识别含「抓/拿/放/移/回零」等词的指令；"
                "物体支持杯子/积木/瓶子/盒子等。更自由说法请在 .env 设 LLM_BACKEND=api"
            )

    note = (llm_config_note or "").strip()
    if note:
        issues.append(note)

    banner = real_robot_safety_banner(
        use_real_robot=use_real_robot,
        robot_backend=robot_backend,
        robot_name=robot_name,
        robot_endpoint=robot_endpoint,
    )
    if use_real_robot:
        ok_items.append(
            f"真机发送：开（通道={robot_name or robot_backend}）— 说指令可能动真臂，请确认周围安全"
        )
        for line in banner.get("lines") or []:
            issues.append(line)
        if (robot_backend or "").lower() == "mock":
            issues.append(
                "真机开关开着，但实际仍是虚拟臂（mock）："
                "请检查 ROBOT_BACKEND 是否为 http/ros，以及地址是否填好"
            )
    else:
        ok_items.append("真机发送：关 — 指令只在虚拟臂执行，真实机械臂不会动（默认、最安全）")

    if rsr_ui or use_rsr_config:
        ok_items.append("Real-Sim-Real（虚实校准）：本次/配置为开（无真机轨迹时用假对照）")
        issues.append("当前校准多半是软件演示；有真实轨迹后才更有科学意义")
    else:
        ok_items.append("Real-Sim-Real（虚实校准）：关")

    return {
        "ready": engine_ok and len([x for x in issues if "引擎未就绪" in x]) == 0,
        "ok_items": ok_items,
        "issues": issues,
        "llm_backend": llm,
        "engine_backend": engine_backend,
        "robot_backend": robot_backend,
        "robot_name": robot_name,
        "use_real_robot": use_real_robot,
        "rsr_on": bool(rsr_ui or use_rsr_config),
        "real_robot_banner": banner,
    }


def capability_markdown(llm_backend: str = "mock") -> str:
    """固定能力边界说明（始终展示）。"""
    llm = (llm_backend or "mock").strip().lower()
    parse_line = (
        "- **语言解析（api）**：说法更自然；动作仍须在白名单内，可输出多步 steps"
        if llm == "api"
        else "- **语言解析（mock）**：需含抓/拿/放/移/回零/等待等；支持「先…再…」多步；物体含杯子、积木等"
    )
    return f"""
### 现在能做什么
{parse_line}
- **动作白名单**：抓 grab / 放 place / 移 move / 回零 home / 等待 wait（详见动作表）
- **多步试机**：一句可编排有序子动作（教学级；失败会标明第几步）
- **场景位姿示意**：接触场景下朝仿真方块坐标伸（不是相机）；默认臂无物体则不编造坐标
- **虚拟执行**：机械臂在仿真里按示意关节运动（能出轨迹与实验数据）
- **经验复用**：同类成功动作可能被再次使用（多步暂不复用）
- **安全闸**：执行前检查关节目标；超限可裁剪（clip）或拒绝（reject）
- **危险拒识**：含「无视限位 / 全速撞」等词会直接拒绝，不会进仿真
- **演示包**：可在「实验数据」区导出一次试机 zip（任务单+轨迹摘要+快照，无密钥）
- **真机**：默认关闭，真实机械臂不会动；只有 `.env` 里打开真发且地址配齐时，才会把同一张任务单（TaskSpec）发出去

### 现在还不能保证什么
- 仿真**不等于**现实精度（有虚实鸿沟是正常的）
- **没有视觉**时，不会自动「看见」红积木坐标再规划
- target（如 red_block）主要是**任务标签**，便于经验/实验记录；不是相机测到的位置
- 真机能不能抓住，取决于实验室接收端与感知，不只取决于本网站

### 三类可演示拦截
1. **胡说**：无动作词（如「点个外卖」）→ `REJECTED`
2. **危险**：无视限位 / 故意撞击等 → `REJECTED`
3. **超限**：关节目标超出模型限位 → `SAFETY_REJECTED`（reject）或裁剪后继续（clip）

### 出问题先看哪里
1. 回复里的「诊断」小节（每次执行后会更新）
2. 本面板的「当前状态 / 需注意」与下方「试一试样例」
3. 代号：`REJECTED`=拒识；`SAFETY_REJECTED`=安全闸拒绝；`ENGINE_TIMEOUT`=仿真超时；`PARSE_FAILED`=解析失败；`INTERNAL`=内部错误
""".strip()


def safety_demo_markdown() -> str:
    """安全闸与拒识的简短说明（面板用）。"""
    return (
        "安全相关演示：点「胡说 / 危险 / 正常」会把句子填入对话并执行；"
        "「超限闸演示」会注入故意超大的关节目标，用于看裁剪或拒绝（不改你的正常聊天习惯）。"
    )


def diagnose_run_result(
    *,
    ok: bool,
    code: str | None,
    message: str | None,
    task_spec: dict[str, Any] | None = None,
    sim_result: dict[str, Any] | None = None,
    robot_result: dict[str, Any] | None = None,
    rsr: dict[str, Any] | None = None,
    safety_gate: dict[str, Any] | None = None,
    experience_hit: bool = False,
    llm_backend: str = "mock",
    use_real_robot: bool = False,
    multi_step: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """根据一次 Pipeline 结果生成可读诊断。"""
    spec = task_spec or {}
    sim = sim_result or {}
    gate = safety_gate or {}
    multi_meta = multi_step if isinstance(multi_step, dict) else {}
    if not gate and isinstance(spec.get("params"), dict):
        # 成功路径也可能只在 params 里留下 audit
        audit = (spec.get("params") or {}).get("safety_audit")
        if isinstance(audit, dict):
            gate = {"safety_audit": audit, "message": (spec.get("params") or {}).get("safety_message")}
    lines: list[str] = []
    level = "success" if ok else "error"

    if ok:
        lines.append("本次执行：成功（虚拟侧已跑通）")
        lines.append(
            f"解析结果：动作={spec.get('action') or '（无）'}，"
            f"目标={spec.get('target') or '（未指定物体名）'}"
        )
        frames = len(sim.get("trajectory") or [])
        lines.append(f"仿真轨迹帧数：{frames}（大于 0 表示臂有运动数据）")
        audit = (gate.get("safety_audit") if isinstance(gate, dict) else None) or {}
        if audit.get("clipped"):
            lines.append(
                "安全闸：已裁剪超限关节目标（原始意图保留在 joint_targets_original，便于日后真机对照）"
            )
        elif audit.get("skipped"):
            lines.append("安全闸：本次无关节目标列表，已跳过限位检查（示意动作路径）")
        elif gate:
            lines.append(f"安全闸：放行 — {gate.get('message') or '目标在限位内'}")
        if not spec.get("target") and not (isinstance(spec.get("steps"), list) and len(spec.get("steps") or []) >= 2):
            lines.append(
                "提示：没有识别到具体物体名。若你说了积木/杯子等仍为空，"
                "可换更明确说法，或改用 LLM_BACKEND=api"
            )
        if experience_hit:
            lines.append("经验库：命中了历史成功经验（同类动作被复用）")
        else:
            lines.append("经验库：未命中（将按本次轨迹学习/记录）")

        # 第14期：多步试机
        sim_metrics = sim.get("metrics") if isinstance(sim.get("metrics"), dict) else {}
        try:
            from core.multi_step_contract import multi_step_diagnosis_lines

            for tip in multi_step_diagnosis_lines(spec, sim_metrics, multi_meta):
                lines.append(tip)
        except Exception:
            pass

        # 第13期：接触试机旁路（来自 sim.metrics）
        try:
            from core.contact_scene_contract import (
                GRASP_PROXY_NO_CONTACT,
                GRASP_PROXY_NO_SCENE,
                GRASP_PROXY_OK,
                contact_trial_diagnosis_lines,
            )

            for tip in contact_trial_diagnosis_lines(sim_metrics):
                lines.append(tip)
            proxy = str(sim_metrics.get("grasp_proxy") or "")
            # 无物体/未接触/代理通过时用 warning 提醒边界，避免误当成「已抓住」
            if proxy in {GRASP_PROXY_NO_SCENE, GRASP_PROXY_NO_CONTACT, GRASP_PROXY_OK} and level == "success":
                level = "warning"
        except Exception:
            pass

        try:
            from core.pose_grounding_contract import pose_grounding_diagnosis_lines

            for tip in pose_grounding_diagnosis_lines(sim_metrics):
                lines.append(tip)
        except Exception:
            pass

        if use_real_robot:
            if isinstance(robot_result, dict) and robot_result.get("ok"):
                lines.append(
                    f"真机通道：已发送成功（{robot_result.get('message') or 'ok'}）—"
                    "请确认实验室侧动作是否符合预期"
                )
            elif isinstance(robot_result, dict):
                level = "warning"
                lines.append(
                    f"真机通道：返回失败 — {robot_result.get('message') or robot_result.get('code') or '未知'}"
                )
            else:
                lines.append("真机通道：已开启，但本次无回执（请看运行配置 / 详细数据）")
        else:
            lines.append("真机通道：关闭 — 真实机械臂不会动（默认安全；只跑了虚拟臂）")

        if isinstance(rsr, dict):
            if rsr.get("ok"):
                mae = (rsr.get("deviation") or {}).get("mae")
                kind = rsr_reference_source_label(rsr.get("reference_source"))
                n = rsr.get("reference_frame_count")
                n_txt = f"，帧数={n}" if n is not None else ""
                pol = rsr_policy_label(
                    rsr.get("policy"),
                    require_real=bool(rsr.get("require_real_trajectory"))
                    if "require_real_trajectory" in rsr
                    else None,
                )
                lines.append(f"RSR 校准：完成（对照={kind}{n_txt}，MAE={mae}｜{pol}）")
                src = str(rsr.get("reference_source") or "").strip().lower()
                if src in {"pseudo_real", "pseudo", "synthetic"}:
                    lines.append(
                        "说明：本次为伪对照（软件演示），不是真机回流；"
                        "有合格真轨迹时会优先用真轨迹。"
                    )
                elif src in {"robot", "real", "real_robot", "true"}:
                    lines.append("说明：本次对照为真轨迹（接收端回传）。")
            elif rsr.get("skipped"):
                pol = rsr_policy_label(rsr.get("policy"))
                tip = f"RSR：跳过 — {rsr.get('message') or '无对照'}（{pol}）"
                er = str(rsr.get("extract_reason") or "").strip()
                if er and "未找到" not in er:
                    tip = tip + f"；轨迹不合格：{er}"
                lines.append(tip)
            else:
                lines.append(f"RSR：未成功 — {rsr.get('message') or '见详细数据'}")
        else:
            lines.append("RSR：未执行（关着则不会做校准；勾选后下次成功执行才会校准）")

        lines.append(
            "请记住：成功 = 意图已解析且仿真已执行；"
            "不代表现实已抓住物体，也不代表仿真物理已与真机完全一致。"
        )
    else:
        code_u = (code or "").upper()
        msg = (message or "").strip() or "执行失败"
        lines.append(f"本次执行：失败 — {msg}")
        if code_u:
            lines.append(f"错误代号：{code_u}")
        # 多步失败定位
        try:
            from core.multi_step_contract import multi_step_diagnosis_lines

            sim_metrics = sim.get("metrics") if isinstance(sim.get("metrics"), dict) else {}
            for tip in multi_step_diagnosis_lines(spec, sim_metrics, multi_meta):
                lines.append(tip)
        except Exception:
            pass
        if code_u in {"REJECTED", "LLM_REJECTED"}:
            # 区分危险拒识 vs 胡说/物体不明
            if "危险" in msg or "不当" in msg:
                lines.append("原因倾向：危险或不当指令（安全拒识）")
                lines.append("建议：不要使用「无视限位 / 全速撞」等说法；改用抓/放/移/回零/等待")
            else:
                lines.append("原因倾向：指令或物体未被当前解析器接受")
                lines.append(f"系统提示：{msg}")
                if (llm_backend or "").lower() != "api":
                    lines.append(
                        "建议：① 动作带「抓/拿/放/移/回零/等待」；"
                        "② 可用「先…再…」多步；"
                        "③ 物体用杯子/积木/瓶子/盒子等；"
                        "④ 或配置 LLM_BACKEND=api"
                    )
                else:
                    lines.append(
                        "建议：换更明确的机械臂动作；action 须为 grab/place/move/home/wait"
                    )
        elif code_u == "SAFETY_REJECTED":
            lines.append("原因倾向：安全闸拒绝 — 关节目标超出模型限位")
            if isinstance(gate, dict) and gate.get("message"):
                lines.append(f"闸说明：{gate.get('message')}")
            lines.append(
                "建议：减小目标角度；或将 SAFETY_MODE=clip 改为裁剪后执行（默认更适合演示）"
            )
        elif code_u == "ENGINE_TIMEOUT":
            lines.append("原因倾向：单次仿真超过墙钟时限")
            lines.append("建议：减少子动作数量，或增大 .env 中 ENGINE_TIMEOUT_SEC")
        elif code_u in {"PARSE_FAILED", "LLM_PARSE_FAILED"}:
            lines.append("原因倾向：解析成 TaskSpec 失败（空指令或模型输出不合法）")
            lines.append("建议：缩短指令、换一种说法；若用 api 请检查密钥与网络")
        elif code_u == "INTERNAL":
            lines.append("原因倾向：内部异常（引擎/存储等）")
            lines.append("建议：重启网站；若反复出现，把本条「详细数据」发给协助者")
        else:
            lines.append("建议：查看下方详细数据中的 code/message；或重启网站再试")

    return {
        "level": level,
        "lines": lines,
        "ok": ok,
        "code": code or "",
        "summary": lines[0] if lines else "",
    }


def format_diagnosis_for_chat(diag: dict[str, Any]) -> str:
    """附加到聊天回复末尾。"""
    lines = diag.get("lines") or []
    if not lines:
        return ""
    return "【诊断】\n" + "\n".join(f"· {x}" for x in lines)
