"""
SkillQuest AI 大模型统一服务（AgentService）

设计原则（第 4 条）：
  - 所有 AI 输出必须结构化 JSON，前端直接渲染。
  - 后端提供统一 AgentService 调用华为云盘古大模型 / 华为云大模型服务。

能力：
  - chat()    : 通用对话，返回模型原始消息文本。
  - chat_json(): 强制结构化输出 —— 将模型回复解析为 dict，校验失败自动
                 重试（要求模型重新输出纯 JSON），最多 max_retries 次。

使用约束：
  - 能规则算的不用大模型（本类不参与任何评分/计算）。
  - LLM 只做生成、分析、解释、推荐。
"""

import json
import re
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from app.core.config import settings


class LLMNotConfiguredError(RuntimeError):
    """华为云大模型未配置 API Key / 端点时的错误。"""


class LLMResponseError(RuntimeError):
    """模型返回内容无法解析为结构化的 JSON 时抛出。"""


def _extract_code_fence(text: str) -> str:
    """剥离模型常见的 ```json ... ``` 代码围栏，提取纯 JSON 片段。"""
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    return fence.group(1).strip() if fence else text.strip()


class LLMService:
    """华为云大模型统一调用服务（Agent 的底层依赖）。"""

    def __init__(self) -> None:
        self.endpoint: str = settings.HUAWEI_LLM_ENDPOINT.rstrip("/")
        self.api_key: str = settings.HUAWEI_LLM_API_KEY
        self.model: str = settings.HUAWEI_LLM_MODEL
        self.auth_type: str = settings.HUAWEI_LLM_AUTH_TYPE
        self.timeout: float = 60.0
        self._client: Optional[httpx.AsyncClient] = None

    # ---------------------------------------------------------------- #
    # 生命周期
    # ---------------------------------------------------------------- #
    async def __aenter__(self) -> "LLMService":
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def is_configured(self) -> bool:
        """LLM 是否已配置（未配置时业务接口应返回友好降级提示）。"""
        return bool(self.api_key and self.endpoint)

    # ---------------------------------------------------------------- #
    # 内部 HTTP
    # ---------------------------------------------------------------- #
    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth_type == "apig":
            headers["X-Apig-AppCode"] = self.api_key
        else:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        """通用多轮对话，返回模型回复的文本内容。"""
        if not self.is_configured:
            raise LLMNotConfiguredError(
                "华为云大模型尚未配置 HUAWEI_LLM_API_KEY / HUAWEI_LLM_ENDPOINT"
            )
        assert self._client is not None, "请使用 async with LLMService() 接入上下文"

        request_body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        }
        url = f"{self.endpoint}/v1/chat/completions"
        resp = await self._client.post(url, json=request_body, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()

        # 兼容主流 OpenAI 协议与盘古 "choices"/"output" 两种返回形态
        choices = data.get("choices") or data.get("output") or []
        if not choices:
            raise LLMResponseError("模型返回中缺少 choices/output 字段")
        first = choices[0]
        content = first.get("message", {}).get("content") or first.get("text") or ""
        return content

    async def chat_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """流式对话（SSE），逐块 yield 模型回复文本。

        - 未配置 LLM 时抛 LLMNotConfiguredError（调用方降级）。
        - 使用独立 AsyncClient，不依赖全局上下文管理器。
        """
        if not self.is_configured:
            raise LLMNotConfiguredError(
                "华为云大模型尚未配置 HUAWEI_LLM_API_KEY / HUAWEI_LLM_ENDPOINT"
            )

        request_body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            "stream": True,
        }
        url = f"{self.endpoint}/v1/chat/completions"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST", url, json=request_body, headers=self._headers()
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[len("data:") :].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        data = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    choices = data.get("choices") or data.get("output") or []
                    for ch in choices:
                        delta = ch.get("delta") or {}
                        piece = (
                            delta.get("content")
                            or delta.get("text")
                            or ch.get("text")
                            or ""
                        )
                        if piece:
                            yield piece

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_hint: str = "",
        temperature: float = 0.1,
        max_tokens: int = 2048,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """结构化输出：要求模型返回纯 JSON，并解析为 dict。

        Args:
            system_prompt: Agent 系统提示词（包含输出格式要求）。
            user_prompt:   本次任务输入（上下文）。
            schema_hint:   JSON Schema 描述，追加到 system 提示中强化约束。
            temperature:   结构化输出通常使用较低温度。
            max_retries:   解析失败后要求模型重新输出的最大次数。

        Returns:
            解析后的结构化 dict。

        Raises:
            LLMNotConfiguredError: 未配置模型。
            LLMResponseError: 多次重试后仍无法解析为 JSON。
        """
        if not self.is_configured:
            raise LLMNotConfiguredError(
                "华为云大模型尚未配置 HUAWEI_LLM_API_KEY / HUAWEI_LLM_ENDPOINT"
            )

        effective_system = system_prompt
        if schema_hint:
            effective_system = (
                f"{system_prompt}\n\n"
                f"【输出 JSON Schema 约束】\n{schema_hint}\n"
                "请严格按此 Schema 返回 JSON，不要包含额外说明文字。"
            )

        last_content = ""
        for attempt in range(max_retries + 1):
            content = await self.chat(
                effective_system, user_prompt, temperature=temperature,
                max_tokens=max_tokens,
            )
            last_content = content
            try:
                parsed = json.loads(_extract_code_fence(content))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
            user_prompt += (
                "\n\n注意：你上一次的输出不是合法 JSON，请只输出符合 Schema 的纯 JSON。"
            )

        raise LLMResponseError(
            f"模型在 {max_retries + 1} 次尝试内均未返回有效 JSON，原始内容："
            f"{last_content[:200]}"
        )


# 全局单例：所有 Agent / 业务模块共用
llm_service = LLMService()