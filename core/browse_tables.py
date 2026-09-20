# -*- coding: utf-8 -*-
"""
实验 / 经验浏览表格（阶段 7）。

独立模块，避免 Streamlit 热重载时对 store 的半旧缓存导致 ImportError。
"""

from __future__ import annotations

from typing import Any

from core.experience_store import list_experiences
from core.experiment_store import list_recent_experiments


def _short_time(iso: str) -> str:
    text = str(iso or "")
    return text.replace("T", " ")[:19] if text else "-"


def _clip(text: str, n: int = 48) -> str:
    s = str(text or "")
    return s[:n] + ("..." if len(s) > n else "")


def _cell_str(value: Any, *, empty: str = "-") -> str:
    """表格单元格统一成字符串，避免 Streamlit/Arrow 混类型报错。"""
    if value is None:
        return empty
    if isinstance(value, float):
        # MAE 等浮点：短小数，避免 object 列混 float/str
        return f"{value:.6g}"
    return str(value) if str(value).strip() != "" else empty


def experiments_table_rows(limit: int = 10) -> list[dict[str, Any]]:
    """网站表格：最近实验（中文列名）。"""
    rows: list[dict[str, Any]] = []
    for item in list_recent_experiments(limit):
        mae = item.get("rsr_mae")
        rows.append(
            {
                "时间(UTC)": _short_time(str(item.get("created_at") or "")),
                "成功": "是" if item.get("ok") else "否",
                "动作": _cell_str(item.get("action")),
                "目标": _cell_str(item.get("target")),
                "引擎": _cell_str(item.get("engine")),
                "模型": _cell_str(item.get("model_ref")),
                "帧数": _cell_str(item.get("frames")),
                "经验命中": "是" if item.get("experience_hit") else "否",
                "含RSR": "是" if item.get("has_rsr") else "否",
                "含真机结果": "是" if item.get("has_robot_result") else "否",
                "RSR_MAE": _cell_str(mae),
                "接触代理": _cell_str(item.get("grasp_proxy")),
                "位姿来源": _cell_str(item.get("pose_source")),
                "指令摘要": _cell_str(item.get("raw_text")),
                "编号": _cell_str(item.get("experiment_id")),
            }
        )
    return rows


def experiences_table_rows(limit: int = 20) -> list[dict[str, Any]]:
    """网站表格：经验条目（中文列名）。"""
    rows: list[dict[str, Any]] = []
    for item in list_experiences(limit):
        rows.append(
            {
                "更新时间(UTC)": _short_time(str(item.get("updated_at") or "")),
                "成功": "是" if item.get("ok") else "否",
                "动作": item.get("action") or "-",
                "目标": item.get("target") or "-",
                "模型": item.get("model_ref") or "-",
                "复用次数": item.get("use_count", 0),
                "轨迹帧数": item.get("trajectory_frames")
                if item.get("trajectory_frames") is not None
                else "-",
                "指令摘要": item.get("raw_text") or "-",
                "键名": item.get("key") or "-",
            }
        )
    return rows
