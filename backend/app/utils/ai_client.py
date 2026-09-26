"""
SkillQuest AI 华为云大模型客户端（预留接口）

SkillQuest AI 的 AI 能力将基于华为云盘古大模型 / 华为云大模型服务实现，覆盖：
  - AI 导师对话
  - 技能诊断与推荐
  - 学习路径生成
  - 自适应练习题生成

当前仅实现基础 HTTP 调用骨架与配置读取，后续接入具体鉴权与模型端点。
"""

from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings


class HuaweiLLMClient:
    """华为云大模型 HTTP 客户端。"""

    def __init__(self) -> None:
        self.endpoint = settings.HUAWEI_LLM_ENDPOINT.rstrip("/")
        self.api_key = settings.HUAWEI_LLM_API_KEY
        self.model = settings.HUAWEI_LLM_MODEL
        self.auth_type = settings.HUAWEI_LLM_AUTH_TYPE
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "HuaweiLLMClient":
        self._client = httpx.AsyncClient(timeout=60.0)
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._client:
            await self._client.aclose()

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth_type == "apig":
            headers["X-Apig-AppCode"] = self.api_key
        else:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        """多轮对话补全（盘古模型接口预留）。

        Args:
            messages: [{"role": "user", "content": "..."}, ...]
            temperature: 采样温度。
            max_tokens: 最大生成长度。

        Returns:
            模型返回体中的关键字段（骨架实现）。

        Raises:
            NotImplementedError: 未配置华为云 API Key 时抛出。
        """
        if not self.api_key:
            raise NotImplementedError(
                "华为云大模型尚未配置 HUAWEI_LLM_API_KEY，"
                "请先在 .env 中填写并将 auth_type/endpoint/model 调整为实际值"
            )

        request_body = {
            "model": self.model,
            "messages": messages,
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        }

        # TODO(接入阶段)：根据实际服务形态调整 URL 路径与返回结构解析
        url = f"{self.endpoint}/v1/chat/completions"
        assert self._client is not None, "请使用 async with 或先调用 __aenter__"
        resp = await self._client.post(
            url, json=request_body, headers=self._build_headers()
        )
        resp.raise_for_status()
        data = resp.json()
        return {"choices": data.get("choices", [])}


# 全局单例
llm_client = HuaweiLLMClient()