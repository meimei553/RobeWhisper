# -*- coding: utf-8 -*-
"""
云端 LLM API 只读自检（能力可见 · 步骤3）

- 未配齐：直接说缺什么，不发网
- 已配齐：发一条极短 Chat Completions，验证密钥/网络/额度
- 绝不把完整密钥写进返回值或页面摘要
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse


def redact_api_base(api_base: str | None) -> dict[str, Any]:
    """地址摘要：只留协议+主机(+端口)+路径尾，便于人看，不含密钥。"""
    raw = str(api_base or "").strip()
    if not raw:
        return {"configured": False, "display": "（未填写地址）", "host": ""}
    try:
        p = urlparse(raw)
        host = p.hostname or ""
        port = f":{p.port}" if p.port else ""
        path = (p.path or "").rstrip("/")
        # 路径太长时只留末段，避免把奇怪 query 带出去
        if p.query or p.fragment:
            path_show = (path.split("/")[-1] or "")[:40]
            display = f"{p.scheme}://{host}{port}/…/{path_show}" if path_show else f"{p.scheme}://{host}{port}"
        else:
            display = f"{p.scheme}://{host}{port}{path}" if host else raw[:60]
        return {"configured": True, "display": display, "host": host}
    except Exception:
        return {"configured": True, "display": "（地址已填，格式需核对）", "host": ""}


def redact_api_key_hint(api_key: str | None) -> str:
    """密钥是否已填的提示，绝不回显原文。"""
    key = str(api_key or "").strip()
    if not key:
        return "未填写"
    # 只给长度档，避免泄漏前缀
    n = len(key)
    if n < 8:
        return "已填（偏短，请核对）"
    return f"已填（约 {n} 位）"


def missing_llm_api_items(
    *,
    api_base: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
) -> list[str]:
    """缺哪些配置项（人话标签）。"""
    missing: list[str] = []
    if not str(api_base or "").strip():
        missing.append("地址 LLM_API_BASE")
    if not str(api_key or "").strip():
        missing.append("密钥 LLM_API_KEY")
    if not str(model_name or "").strip():
        missing.append("模型名 LLM_MODEL_NAME")
    return missing


def _chat_url(api_base: str) -> str:
    base = str(api_base or "").strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def probe_llm_api(
    *,
    api_base: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
    timeout_sec: float = 8.0,
    use_settings: bool = True,
) -> dict[str, Any]:
    """
    只读探测云端 API 是否通。

    返回：ok, code, message, base_redacted, key_hint, model, http_status, missing, read_only
    """
    if use_settings and (api_base is None or api_key is None or model_name is None):
        from config.safe import setting

        if api_base is None:
            api_base = str(setting("LLM_API_BASE", "") or "")
        if api_key is None:
            api_key = str(setting("LLM_API_KEY", "") or "")
        if model_name is None:
            model_name = str(setting("LLM_MODEL_NAME", "") or "")

    base = str(api_base or "").strip()
    key = str(api_key or "").strip()
    model = str(model_name or "").strip()
    base_red = redact_api_base(base)
    key_hint = redact_api_key_hint(key)
    missing = missing_llm_api_items(api_base=base, api_key=key, model_name=model)

    common: dict[str, Any] = {
        "base_redacted": base_red,
        "key_hint": key_hint,
        "model": model or "（未填）",
        "http_status": None,
        "missing": missing,
        "read_only": True,
        "detail": {},
    }

    if missing:
        return {
            **common,
            "ok": False,
            "code": "NOT_CONFIGURED",
            "message": "还缺：" + "、".join(missing) + "。先在 .env 补齐并重启网站，再点自检。",
        }

    # 极短探测：不走机器人指令解析，只验证「密钥+网络+模型」
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": 8,
        "messages": [
            {"role": "user", "content": "只回复一个字：通"},
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _chat_url(base),
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=float(timeout_sec)) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = int(getattr(resp, "status", 200) or 200)
        data: Any
        try:
            data = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            data = {}
        # 有 choices 即视为通；部分网关只回 id 也算成功
        has_choice = isinstance(data, dict) and bool(data.get("choices"))
        if status < 400 and (has_choice or isinstance(data, dict)):
            tip = "云端 API 看起来通了（只读探测成功）。这不代表额度永远够用。"
            if has_choice:
                tip = "云端 API 看起来通了：密钥与模型可调用（只读探测，未跑机械臂）。"
            return {
                **common,
                "ok": True,
                "code": "OK",
                "message": tip,
                "http_status": status,
                "detail": {"has_choices": has_choice},
            }
        return {
            **common,
            "ok": False,
            "code": "HTTP_ERROR",
            "message": f"对方返回了 HTTP {status}。请核对 LLM_API_BASE 是否写成 …/v1 这类根地址。",
            "http_status": status,
        }
    except TimeoutError:
        return {
            **common,
            "ok": False,
            "code": "TIMEOUT",
            "message": "等待超时。请检查网络、代理，或稍后再试。",
        }
    except urllib.error.HTTPError as exc:
        code = int(exc.code)
        detail_msg = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
            err_json = json.loads(err_body) if err_body.strip() else {}
            detail_msg = str(((err_json.get("error") or {}) if isinstance(err_json, dict) else {}).get("message") or "")
        except Exception:
            detail_msg = ""
        if code == 401 or code == 403:
            return {
                **common,
                "ok": False,
                "code": "AUTH",
                "message": "密钥无效或无权限。请核对 .env 里的 LLM_API_KEY（页面不会显示密钥原文）。",
                "http_status": code,
            }
        if code == 429:
            msg = "额度不足或请求太频繁。请到服务商控制台充值/稍后再试。"
            if detail_msg:
                msg = msg + f"（{detail_msg[:60]}）"
            return {
                **common,
                "ok": False,
                "code": "QUOTA",
                "message": msg,
                "http_status": code,
            }
        if code == 404:
            return {
                **common,
                "ok": False,
                "code": "NOT_FOUND",
                "message": "地址路径可能不对（404）。常见写法是 https://…/v1（不要漏 /v1）。",
                "http_status": code,
            }
        return {
            **common,
            "ok": False,
            "code": "HTTP_ERROR",
            "message": f"对方返回 HTTP {code}。请核对地址与模型名是否匹配该服务商。",
            "http_status": code,
        }
    except urllib.error.URLError:
        return {
            **common,
            "ok": False,
            "code": "NETWORK",
            "message": "连不上云端。请检查网络、防火墙，或 LLM_API_BASE 是否写错。",
        }
    except Exception:
        return {
            **common,
            "ok": False,
            "code": "INTERNAL",
            "message": "自检时出了点问题。请核对 .env 三项配置；网站仍可用 mock 演示。",
        }
