# -*- coding: utf-8 -*-
"""
运行环境快照（第 10 期 · 步骤 1）

纯函数：收集可复现实验用的非机密配置与适配器版本。
写入实验旁路字段 run_snapshot，不改 TaskSpec 主字段。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# 快照 schema；只增不改语义，便于旧记录兼容
RUN_SNAPSHOT_SCHEMA_VERSION = 1

# 绝对不得进入快照的键名（大小写不敏感子串匹配）
_SECRET_KEY_MARKERS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "secret",
    "password",
    "token",
    "authorization",
    "private_key",
    "access_key",
)


def _is_secret_key(name: str) -> bool:
    low = str(name or "").strip().lower().replace("-", "_")
    return any(m in low for m in _SECRET_KEY_MARKERS)


def _adapter_info(obj: Any, fallback_name: str = "unknown") -> dict[str, str]:
    """从适配器对象或 dict 提取 name/version；缺失给占位。"""
    if obj is None:
        return {"name": fallback_name, "version": "unknown"}
    if isinstance(obj, dict):
        name = str(obj.get("name") or fallback_name)
        ver = str(obj.get("version") or obj.get("engine_version") or "unknown")
        return {"name": name or fallback_name, "version": ver or "unknown"}
    name = str(getattr(obj, "name", None) or fallback_name)
    ver = str(getattr(obj, "version", None) or "unknown")
    # 部分适配器只有 name，无 version 属性
    if ver == "unknown" and hasattr(obj, "version"):
        try:
            ver = str(obj.version)
        except Exception:
            ver = "unknown"
    return {"name": name or fallback_name, "version": ver or "unknown"}


def _safe_setting(name: str, default: Any = None) -> Any:
    try:
        from config.safe import setting

        return setting(name, default)
    except Exception:
        return default


def _str_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def collect_run_snapshot(
    *,
    adapters: dict[str, Any] | None = None,
    llm: Any = None,
    engine: Any = None,
    robot: Any = None,
    model_ref: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    组装运行快照（可 JSON 序列化）。

    adapters: 可选 {llm, engine, robot} 名称字符串（Pipeline 里常见）
    llm/engine/robot: 可选适配器实例，用于读取 version
    model_ref: 当前臂/场景模型引用
    extra: 仅合并非机密键；命中密钥标记的键会被丢弃
    """
    adapters = dict(adapters or {})

    llm_info = _adapter_info(llm, str(adapters.get("llm") or "unknown"))
    engine_info = _adapter_info(engine, str(adapters.get("engine") or "unknown"))
    robot_info = _adapter_info(robot, str(adapters.get("robot") or "unknown"))
    # 若只有 adapters 字符串、无实例，保留名称
    if llm is None and adapters.get("llm"):
        llm_info["name"] = str(adapters["llm"])
    if engine is None and adapters.get("engine"):
        engine_info["name"] = str(adapters["engine"])
    if robot is None and adapters.get("robot"):
        robot_info["name"] = str(adapters["robot"])

    model = str(model_ref if model_ref is not None else _safe_setting("DEFAULT_MODEL_REL", "default") or "default")

    backends = {
        "ENGINE_BACKEND": str(_safe_setting("ENGINE_BACKEND", "") or ""),
        "LLM_BACKEND": str(_safe_setting("LLM_BACKEND", "") or ""),
        "ROBOT_BACKEND": str(_safe_setting("ROBOT_BACKEND", "") or ""),
    }

    flags = {
        "USE_REAL_ROBOT": _str_flag(_safe_setting("USE_REAL_ROBOT", False)),
        "USE_REAL_SIM_REAL": _str_flag(_safe_setting("USE_REAL_SIM_REAL", False)),
        "SAFETY_MODE": str(_safe_setting("SAFETY_MODE", "clip") or "clip"),
    }

    timeouts = {
        "ENGINE_TIMEOUT_SEC": float(_safe_setting("ENGINE_TIMEOUT_SEC", 30) or 30),
        "LLM_TIMEOUT_SEC": float(_safe_setting("LLM_TIMEOUT_SEC", 60) or 60),
        "ROBOT_TIMEOUT_SEC": float(_safe_setting("ROBOT_TIMEOUT_SEC", 30) or 30),
    }

    # 模型相对路径（非绝对盘符隐私最小化；只记配置项名）
    paths = {
        "DEFAULT_MODEL_REL": str(_safe_setting("DEFAULT_MODEL_REL", "") or ""),
        "MODELS_DIR_NAME": "models",
    }

    # 真机桥旁路：主机名脱敏，不含密钥（第 11 期）
    robot_bridge: dict[str, Any] = {}
    try:
        from core.robot_bridge_contract import collect_robot_bridge_snapshot

        robot_bridge = collect_robot_bridge_snapshot()
    except Exception:
        robot_bridge = {
            "backend": str(_safe_setting("ROBOT_BACKEND", "") or ""),
            "use_real_robot": _str_flag(_safe_setting("USE_REAL_ROBOT", False)),
            "endpoint": {"configured": False},
        }

    safe_extra: dict[str, Any] = {}
    for key, value in dict(extra or {}).items():
        if _is_secret_key(str(key)):
            continue
        # 值里也不要塞疑似密钥
        if isinstance(value, str) and value.strip().lower().startswith("sk-"):
            continue
        safe_extra[str(key)] = value

    snap: dict[str, Any] = {
        "schema_version": RUN_SNAPSHOT_SCHEMA_VERSION,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "model_ref": model,
        "backends": backends,
        "adapters": {
            "llm": llm_info,
            "engine": engine_info,
            "robot": robot_info,
        },
        "flags": flags,
        "timeouts": timeouts,
        "paths": paths,
        "robot_bridge": robot_bridge,
    }
    if safe_extra:
        snap["extra"] = safe_extra
    return snap


def snapshot_contains_secrets(snapshot: dict[str, Any]) -> list[str]:
    """
    自检：返回可疑路径列表（空列表=通过）。
    用于烟雾与导出前脱敏复核。
    """
    hits: list[str] = []

    def walk(obj: Any, path: str) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                p = f"{path}.{k}" if path else str(k)
                if _is_secret_key(str(k)):
                    hits.append(p)
                if isinstance(v, str) and "sk-" in v.lower():
                    hits.append(p)
                walk(v, p)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")

    walk(snapshot, "")
    return hits
