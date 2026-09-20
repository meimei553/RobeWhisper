# -*- coding: utf-8 -*-
"""
真机桥最小 JSON 契约（第 11 期 · 步骤 1）

请求：RobeWhisper → 实验室执行节点
响应：执行节点 → RobeWhisper（ack；trajectory 可选，留给第 12 期）

不改 TaskSpec 主字段；旁路字段只增不改语义。
"""

from __future__ import annotations

from typing import Any

from core.schemas import TaskSpec

# 请求外层键（固定）
REQUEST_SOURCE = "robewhisper"
REQUEST_KEYS = ("task_spec", "source")

# 响应最小键：ok / message；其余可增
ACK_REQUIRED_KEYS = ("ok", "message")

# 第 12 期预留：真机轨迹（本期可不返回）
OPTIONAL_TRAJECTORY_KEY = "trajectory"


def build_execute_request(task: TaskSpec | dict[str, Any]) -> dict[str, Any]:
    """组装发给真机桥的 POST / topic 载荷。"""
    if isinstance(task, TaskSpec):
        spec = task.to_dict()
    else:
        spec = dict(task or {})
    return {
        "task_spec": spec,
        "source": REQUEST_SOURCE,
    }


def validate_execute_request(payload: dict[str, Any] | None) -> tuple[bool, str]:
    """检查请求是否满足最小契约。返回 (ok, 中文说明)。"""
    data = payload if isinstance(payload, dict) else {}
    if "task_spec" not in data:
        return False, "缺少 task_spec"
    spec = data.get("task_spec")
    if not isinstance(spec, dict):
        return False, "task_spec 必须是对象"
    # 主字段名必须能被 TaskSpec 识别（允许缺省值）
    try:
        ts = TaskSpec.from_dict(spec)
    except Exception:
        return False, "task_spec 无法解析为 TaskSpec"
    if not str(ts.action or "").strip():
        return False, "task_spec.action 不能为空"
    src = data.get("source")
    if src is not None and str(src) != REQUEST_SOURCE:
        # 允许缺省 source；若提供则建议为 robewhisper
        pass
    return True, "请求契约通过"


def normalize_execute_ack(raw: dict[str, Any] | None) -> dict[str, Any]:
    """
    把实验室返回整理成统一 ack（只增字段，不删实验室自定义键的副本）。
    最小：ok, message；可选：trajectory, code, data
    """
    data = dict(raw or {})
    ok = bool(data.get("ok", True))
    # 若显式失败码且无 ok，视为失败
    if "ok" not in data and str(data.get("code") or "").upper() not in {"", "OK"}:
        ok = False
    message = str(data.get("message") or ("真机侧已确认" if ok else "真机侧失败"))
    out: dict[str, Any] = {
        "ok": ok,
        "message": message,
        "schema": "robewhisper_robot_ack_v1",
    }
    if "code" in data:
        out["code"] = data.get("code")
    if OPTIONAL_TRAJECTORY_KEY in data:
        # 原样保留，第 12 期再用；本期不强制校验形状
        out[OPTIONAL_TRAJECTORY_KEY] = data.get(OPTIONAL_TRAJECTORY_KEY)
    # 实验室额外字段进 extras，避免冲掉主契约理解
    reserved = {"ok", "message", "code", OPTIONAL_TRAJECTORY_KEY, "schema"}
    extras = {k: v for k, v in data.items() if k not in reserved}
    if extras:
        out["extras"] = extras
    return out


def validate_execute_ack(payload: dict[str, Any] | None) -> tuple[bool, str]:
    """检查响应是否至少含 ok + message（布尔/可转布尔 + 字符串）。"""
    data = payload if isinstance(payload, dict) else {}
    if "ok" not in data:
        return False, "响应缺少 ok"
    if "message" not in data:
        return False, "响应缺少 message"
    if not isinstance(data.get("message"), str):
        return False, "message 应为字符串"
    # trajectory 可选
    traj = data.get(OPTIONAL_TRAJECTORY_KEY)
    if traj is not None and not isinstance(traj, list):
        return False, "若提供 trajectory，应为列表（留给第12期）"
    return True, "响应契约通过"


def task_spec_main_fields() -> set[str]:
    """TaskSpec 主字段集合（红线：本期不改名）。"""
    return set(TaskSpec(task_id="a", action="m").to_dict().keys())


def redact_robot_endpoint(endpoint: str | None) -> dict[str, Any]:
    """
    把 ROBOT_EXECUTE_ENDPOINT 脱敏成旁路摘要（无用户名/密码/查询串）。
    便于答辩展示「发过哪台主机」，不含密钥。
    """
    from urllib.parse import urlparse

    raw = str(endpoint or "").strip()
    if not raw:
        return {"configured": False, "host": "", "port": None, "path": "", "scheme": ""}
    try:
        parsed = urlparse(raw)
        host = str(parsed.hostname or "")
        port = parsed.port
        path = str(parsed.path or "")
        scheme = str(parsed.scheme or "")
        return {
            "configured": bool(host or path),
            "scheme": scheme,
            "host": host,
            "port": port,
            "path": path,
            # 展示用短串，绝不带 userinfo / query / fragment
            "display": f"{scheme}://{host}"
            + (f":{port}" if port else "")
            + path,
        }
    except Exception:
        return {"configured": False, "host": "", "port": None, "path": "", "scheme": "", "display": ""}


def sanitize_robot_result_for_store(robot_result: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    实验旁路用的 robot_result：保留成败与 ack，脱敏 endpoint 完整 URL。
    不吞原始 TaskSpec（本函数不碰 task_spec）。
    """
    if not isinstance(robot_result, dict):
        return None
    out = dict(robot_result)
    data = out.get("data")
    if isinstance(data, dict):
        data2 = dict(data)
        if "endpoint" in data2:
            data2["endpoint_redacted"] = redact_robot_endpoint(str(data2.get("endpoint") or ""))
            del data2["endpoint"]
        # 响应里若误带密钥键，丢掉
        for drop in list(data2.keys()):
            low = str(drop).lower()
            if any(m in low for m in ("api_key", "token", "password", "secret")):
                del data2[drop]
        out["data"] = data2
    return out


def collect_robot_bridge_snapshot() -> dict[str, Any]:
    """写入 run_snapshot 的真机桥摘要（非机密）。"""
    try:
        from config.safe import setting

        backend = str(setting("ROBOT_BACKEND", "mock") or "mock")
        use_real = bool(setting("USE_REAL_ROBOT", False))
        endpoint = str(setting("ROBOT_EXECUTE_ENDPOINT", "") or "")
    except Exception:
        backend, use_real, endpoint = "mock", False, ""
    return {
        "backend": backend,
        "use_real_robot": use_real,
        "endpoint": redact_robot_endpoint(endpoint),
    }
