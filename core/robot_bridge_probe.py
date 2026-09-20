# -*- coding: utf-8 -*-
"""
真机 HTTP 桥只读自检（第 11 期 · 步骤 4）

只发 GET（探测「对方在不在线」），不发任务单、不发抓/放等动作。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse, urlunparse

from core.robot_bridge_contract import redact_robot_endpoint


def _normalize_probe_url(endpoint: str) -> str:
    """用配置的 execute 地址做探测；去掉 query/fragment，避免把密钥带出去。"""
    raw = str(endpoint or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    # 去掉 userinfo / query / fragment
    clean = parsed._replace(netloc=parsed.hostname or "", query="", fragment="")
    if parsed.port:
        host = parsed.hostname or ""
        clean = clean._replace(netloc=f"{host}:{parsed.port}")
    return urlunparse(clean)


def probe_http_bridge(
    endpoint: str | None = None,
    *,
    timeout_sec: float = 3.0,
) -> dict[str, Any]:
    """
    只读探测 HTTP 接收端是否在线。

    返回：
      ok, code, message, endpoint_redacted, http_status, detail
    """
    from config.safe import setting

    ep = str(endpoint if endpoint is not None else setting("ROBOT_EXECUTE_ENDPOINT", "") or "").strip()
    redacted = redact_robot_endpoint(ep)
    if not ep:
        return {
            "ok": False,
            "code": "NOT_CONFIGURED",
            "message": "还没填写 ROBOT_EXECUTE_ENDPOINT（接收端网址）。先在 .env 里写上再测。",
            "endpoint_redacted": redacted,
            "http_status": None,
            "detail": {},
            "read_only": True,
        }

    url = _normalize_probe_url(ep)
    req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=float(timeout_sec)) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = int(getattr(resp, "status", 200) or 200)
        body: Any
        try:
            body = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            body = {"raw_preview": raw[:120]}

        # 200 即视为「有人在听」；对方若只支持 POST，也可能 405，见下方分支
        if status < 400:
            tip = "桥看起来通了（只读探测成功）。这不代表已经发过抓取指令。"
            if isinstance(body, dict) and body.get("message"):
                tip = f"桥看起来通了：{body.get('message')}（只读探测，未发任务单）"
            return {
                "ok": True,
                "code": "OK",
                "message": tip,
                "endpoint_redacted": redacted,
                "http_status": status,
                "detail": {"body": body} if isinstance(body, dict) else {"body": str(body)[:200]},
                "read_only": True,
            }
        return {
            "ok": False,
            "code": "HTTP_ERROR",
            "message": f"对方返回了 HTTP {status}。请确认网址路径是否为 /execute_task。",
            "endpoint_redacted": redacted,
            "http_status": status,
            "detail": {},
            "read_only": True,
        }
    except urllib.error.HTTPError as exc:
        code = int(exc.code)
        # 405 Method Not Allowed：很多真接收端只收 POST，但说明端口/服务在
        if code in {405, 501}:
            return {
                "ok": True,
                "code": "REACHABLE_POST_ONLY",
                "message": (
                    f"对方在线，但可能只接受 POST（探测收到 HTTP {code}）。"
                    "这通常也算桥通了；真正发任务要等你开真发并说指令。"
                ),
                "endpoint_redacted": redacted,
                "http_status": code,
                "detail": {},
                "read_only": True,
            }
        if code == 404:
            return {
                "ok": False,
                "code": "NOT_FOUND",
                "message": "网址路径可能不对（404）。请核对是否写成 …/execute_task。",
                "endpoint_redacted": redacted,
                "http_status": code,
                "detail": {},
                "read_only": True,
            }
        return {
            "ok": False,
            "code": "HTTP_ERROR",
            "message": f"对方返回 HTTP {code}。请让实验室确认接收端是否已启动。",
            "endpoint_redacted": redacted,
            "http_status": code,
            "detail": {},
            "read_only": True,
        }
    except TimeoutError:
        return {
            "ok": False,
            "code": "TIMEOUT",
            "message": "等待超时。请检查对方电脑是否开机、地址/端口是否写对、防火墙是否拦了。",
            "endpoint_redacted": redacted,
            "http_status": None,
            "detail": {},
            "read_only": True,
        }
    except urllib.error.URLError:
        return {
            "ok": False,
            "code": "NETWORK",
            "message": "连不上对方。常见原因：假接收端没开、IP 写错、对方程序没启动。",
            "endpoint_redacted": redacted,
            "http_status": None,
            "detail": {},
            "read_only": True,
        }
    except Exception:
        return {
            "ok": False,
            "code": "INTERNAL",
            "message": "自检时出了点问题。请核对 .env 里的网址，或先关真发用虚拟臂。",
            "endpoint_redacted": redacted,
            "http_status": None,
            "detail": {},
            "read_only": True,
        }
