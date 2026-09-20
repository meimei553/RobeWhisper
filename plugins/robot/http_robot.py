# -*- coding: utf-8 -*-
"""
HTTP 真机桥：将 TaskSpec JSON POST 到 ROBOT_EXECUTE_ENDPOINT。

用于无 ROS 环境下的联调；失败返回友好 ApiResult，不抛堆栈。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from config import settings
from core.robot_bridge_contract import build_execute_request, normalize_execute_ack
from core.schemas import ApiResult, TaskSpec
from plugins.robot.base import BaseRobot

FRIENDLY_BLOCKED = "思考遇到一些阻碍，请稍后再试。"


class HttpRobot(BaseRobot):
    """Open 风格 HTTP execute_task 适配器。"""

    def __init__(
        self,
        endpoint: str | None = None,
        timeout_sec: int | None = None,
    ) -> None:
        self._endpoint = (endpoint if endpoint is not None else settings.ROBOT_EXECUTE_ENDPOINT).strip()
        self._timeout = int(
            timeout_sec if timeout_sec is not None else settings.ROBOT_TIMEOUT_SEC
        )

    @property
    def name(self) -> str:
        return "http_robot"

    def execute_task(self, task: TaskSpec) -> ApiResult:
        if not task.action:
            return ApiResult.fail("REJECTED", FRIENDLY_BLOCKED)
        if not self._endpoint:
            return ApiResult.fail("INTERNAL", "未配置 ROBOT_EXECUTE_ENDPOINT。")

        # 与 robot_bridge_contract 同一套请求载荷
        payload: dict[str, Any] = build_execute_request(task)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self._endpoint,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                status = getattr(resp, "status", 200)
            data: dict[str, Any]
            try:
                parsed = json.loads(raw) if raw.strip() else {}
                data = parsed if isinstance(parsed, dict) else {"raw": raw}
            except json.JSONDecodeError:
                data = {"raw": raw}

            if status >= 400:
                return ApiResult.fail(
                    "NETWORK",
                    FRIENDLY_BLOCKED,
                    data={"http_status": status, "robot": self.name, "response": data},
                )

            # 统一 ack；对端可返旧字段，normalize 会补齐 message
            ack = normalize_execute_ack(data)
            if not bool(ack.get("ok", True)):
                return ApiResult.fail(
                    "REJECTED",
                    str(ack.get("message") or FRIENDLY_BLOCKED),
                    data={
                        "accepted": False,
                        "task_id": task.task_id,
                        "robot": self.name,
                        "endpoint": self._endpoint,
                        "http_status": status,
                        "ack": ack,
                        "response": data,
                    },
                )

            return ApiResult.success(
                f"HTTP 真机桥已投递 action={task.action}",
                data={
                    "accepted": True,
                    "task_id": task.task_id,
                    "robot": self.name,
                    "endpoint": self._endpoint,
                    "http_status": status,
                    "ack": ack,
                    "response": data,
                },
            )
        except TimeoutError:
            return ApiResult.fail("TIMEOUT", FRIENDLY_BLOCKED, data={"robot": self.name})
        except urllib.error.HTTPError as exc:
            return ApiResult.fail(
                "NETWORK",
                FRIENDLY_BLOCKED,
                data={"robot": self.name, "http_status": int(exc.code)},
            )
        except urllib.error.URLError:
            return ApiResult.fail("NETWORK", FRIENDLY_BLOCKED, data={"robot": self.name})
        except Exception:
            return ApiResult.fail("INTERNAL", FRIENDLY_BLOCKED, data={"robot": self.name})
