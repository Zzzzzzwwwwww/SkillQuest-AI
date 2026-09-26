"""
SkillQuest AI Agent 基类与执行器

- BaseAgent    : 业务 Agent 的抽象基类（绑定 AgentSpec 与 LLMService）。
- AgentRunner  : 统一执行入口，对未配置大模型场景提供友好降级
                 （返回错误结构化信息，前端可渲染成提示卡片）。

后续各业务模块（测评、图谱、导学、答疑、评估、督导、复盘）将
继承 BaseAgent 实现 run()。
"""

import json
from abc import ABC
from typing import Any, Dict, Optional

from app.agents.prompts import AgentSpec
from app.services.llm import LLMNotConfiguredError, LLMResponseError, LLMService


class BaseAgent(ABC):
    """业务 Agent 基类。"""

    # 具体 Agent 通过类属性绑定定义
    spec: AgentSpec
    _llm: Optional[LLMService] = None

    @classmethod
    def bind_llm(cls, llm: LLMService) -> None:
        """绑定共享的 LLMService 实例。"""
        cls._llm = llm

    @property
    def llm(self) -> LLMService:
        if self._llm is None:
            self._llm = LLMService()
        return self._llm

    def build_user_prompt(self, payload: Dict[str, Any]) -> str:
        """把业务输入序列化为模型输入（子类可覆写做格式化）。"""
        return json.dumps(payload, ensure_ascii=False, indent=2)

    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """执行 Agent：调用大模型并返回结构化 JSON。

        Args:
            payload: 业务上下文参数（数值统计一律由系统规则计算后传入）。

        Returns:
            结构化结果 dict；未配置大模型时返回降级结构。
        """
        try:
            return await self.llm.chat_json(
                system_prompt=self.spec.combined_prompt,
                user_prompt=self.build_user_prompt(payload),
                schema_hint=self.spec.json_schema,
            )
        except (LLMNotConfiguredError, LLMResponseError) as exc:
            return self.degraded_result(str(exc))

    def degraded_result(self, reason: str) -> Dict[str, Any]:
        """大模型不可用时的降级输出：保证前端仍能稳定渲染。"""
        return {
            "agent": self.spec.name,
            "ok": False,
            "error": reason,
            "note": "当前为骨架降级响应：模型未接入或返回异常，业务输出将在后续模块实现。",
        }


class AgentRunner:
    """多智能体统一调度入口。

    用法：
        runner = AgentRunner(llm_service)
        result = await runner.run("tutor", {"question": "..."})
    """

    def __init__(self, llm: Optional[LLMService] = None) -> None:
        self.llm = llm or LLMService()
        self._cache: Dict[str, type] = {}

    def register(self, agent_cls: type) -> "AgentRunner":
        """注册 Agent 类（由模块初始化时调用）。"""
        self._cache[agent_cls.spec.name] = agent_cls
        return self

    async def run(self, agent_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """按名称调度 Agent 并执行。"""
        agent_cls = self._cache.get(agent_name)
        if agent_cls is None:
            return {
                "agent": agent_name,
                "ok": False,
                "error": f"未注册的 Agent: {agent_name}",
            }
        agent_cls.bind_llm(self.llm)
        return await agent_cls().run(payload)

    @property
    def registered(self) -> list[str]:
        return list(self._cache.keys())


# 全局共享执行器（业务模块注册后使用）
agent_runner = AgentRunner()