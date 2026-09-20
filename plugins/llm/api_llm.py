# -*- coding: utf-8 -*-
"""
云端 LLM 适配器骨架（OpenAI 兼容 Chat Completions）。

只用标准库发 HTTP，不绑定单一厂商 SDK。
配置来自 config.settings：LLM_API_BASE / LLM_API_KEY / LLM_MODEL_NAME。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from config import settings
from core.instruction_guard import reject_if_dangerous
from core.schemas import ApiResult
from plugins.llm.base import (
    FRIENDLY_BLOCKED,
    BaseLLM,
    LLM_CODE_INTERNAL,
    LLM_CODE_NETWORK,
    LLM_CODE_PARSE_FAILED,
    LLM_CODE_TIMEOUT,
)
from plugins.llm.json_extract import parse_model_text_to_task
from plugins.llm.prompt import SYSTEM_PROMPT


class ApiLLM(BaseLLM):
    """OpenAI 兼容 API；缺配置或网络失败时返回友好 ApiResult，不抛堆栈。"""

    def __init__(
        self,
        api_base: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout_sec: int | None = None,
    ) -> None:
        self._api_base = (api_base if api_base is not None else settings.LLM_API_BASE).rstrip("/")
        self._api_key = api_key if api_key is not None else settings.LLM_API_KEY
        self._model_name = model_name if model_name is not None else settings.LLM_MODEL_NAME
        self._timeout = int(timeout_sec if timeout_sec is not None else settings.LLM_TIMEOUT_SEC)

    @property
    def name(self) -> str:
        return "api_llm"

    def is_configured(self) -> bool:
        return bool(self._api_base and self._api_key and self._model_name)

    def _chat_url(self) -> str:
        base = self._api_base
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    def _request_chat(self, user_text: str) -> ApiResult:
        if not self.is_configured():
            return ApiResult.fail(LLM_CODE_INTERNAL, "大模型未配置，请检查 API 地址、密钥与模型名。")

        payload: dict[str, Any] = {
            "model": self._model_name,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._chat_url(),
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            if not str(content).strip():
                return ApiResult.fail(LLM_CODE_PARSE_FAILED, FRIENDLY_BLOCKED)
            return ApiResult.success("api_raw", data={"content": str(content)})
        except TimeoutError:
            return ApiResult.fail(LLM_CODE_TIMEOUT, FRIENDLY_BLOCKED)
        except urllib.error.HTTPError as exc:
            # 429/401 等给出可读原因，避免一律当成断网
            try:
                body = exc.read().decode("utf-8", errors="replace")
                detail = str((json.loads(body).get("error") or {}).get("message") or "")
            except Exception:
                detail = ""
            if exc.code == 429:
                msg = "大模型额度不足或账号暂停，请到 Moonshot 控制台充值后再试。"
                if detail:
                    msg = msg + f"（{detail[:80]}）"
                return ApiResult.fail(LLM_CODE_NETWORK, msg)
            if exc.code in {401, 403}:
                return ApiResult.fail(
                    LLM_CODE_INTERNAL,
                    "大模型密钥无效或无权限，请检查 .env 中的 LLM_API_KEY。",
                )
            return ApiResult.fail(LLM_CODE_NETWORK, FRIENDLY_BLOCKED)
        except urllib.error.URLError:
            return ApiResult.fail(LLM_CODE_NETWORK, FRIENDLY_BLOCKED)
        except Exception:
            return ApiResult.fail(LLM_CODE_INTERNAL, FRIENDLY_BLOCKED)

    def parse_instruction(self, text: str, task_id: str) -> ApiResult:
        raw = (text or "").strip()
        if not raw:
            return ApiResult.fail(LLM_CODE_PARSE_FAILED, FRIENDLY_BLOCKED)

        # 危险词在调用云端前拦截，避免「模型仍可能编造危险动作」
        blocked = reject_if_dangerous(raw)
        if blocked is not None:
            return blocked

        chat = self._request_chat(raw)
        if not chat.ok:
            return chat

        content = str((chat.data or {}).get("content", ""))
        return parse_model_text_to_task(content, task_id=task_id, raw_user=raw, source="llm")
