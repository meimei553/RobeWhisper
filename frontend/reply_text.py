# -*- coding: utf-8 -*-
"""聊天回复文案（阶段 7 · 步骤 2）：与 Streamlit 解耦，便于烟雾测试。"""

from __future__ import annotations

FRIENDLY_BLOCKED = "思考遇到一些阻碍，请稍后再试。"


def format_success_reply(
    message: str,
    *,
    action: str,
    target: str,
    frame_count: int,
    experience_hit: bool,
    experiment_id: str,
    robot_name: str,
    robot_msg: str,
    rsr_msg: str,
    contact_msg: str = "",
    multi_step_msg: str = "",
    pose_msg: str = "",
    diagnosis: str = "",
) -> str:
    """把执行结果收成更易读的几行中文（少堆原始字段名）。"""
    lines = [
        str(message or "指令已执行"),
        f"动作：{action or '（未知）'}｜目标：{target or '（无）'}｜轨迹帧数：{frame_count}",
        f"经验复用：{'是' if experience_hit else '否'}｜实验编号：{experiment_id or '（无）'}",
        f"机器人通道：{robot_name or '（无）'}"
        + (f"（{robot_msg}）" if robot_msg else ""),
    ]
    if multi_step_msg:
        lines.append(f"多步试机：{multi_step_msg}")
    if pose_msg:
        lines.append(f"场景位姿示意：{pose_msg}")
    lines.append(f"Real-Sim-Real：{rsr_msg}")
    if contact_msg:
        lines.append(f"接触试机：{contact_msg}")
    text = "\n".join(lines)
    if diagnosis:
        text = text + "\n\n" + diagnosis
    return text


def format_fail_reply(message: str | None, code: str | None, diagnosis: str = "") -> str:
    """失败时优先友好文案，代码仅作补充。"""
    text = (message or "").strip() or FRIENDLY_BLOCKED
    if code and code not in {"OK", ""} and code not in text:
        text = f"{text}\n（代号：{code}）"
    if diagnosis:
        text = text + "\n\n" + diagnosis
    return text
