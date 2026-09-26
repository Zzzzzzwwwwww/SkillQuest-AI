"""
SkillQuest AI 统一多智能体 Schema。

约定：
  - POST /agents/run    —— 统一入参 AgentRunIn，出参为结构化 JSON（成功）或降级标记；
  - POST /agents/stream —— SSE 流式（event：delta / done）；
  - GET  /agents        —— Agent 清单（供前端/调试展示）。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# 合法 Agent 类型（与 AGENT_REGISTRY 对齐，供 Pydantic 校验提示）
AVAILABLE_AGENT_TYPES = (
    "orchestrator",
    "career",
    "skill",
    "learning",
    "tutor",
    "assessment",
    "coach",
    "reflection",
)


class AgentRunIn(BaseModel):
    """统一 Agent 入参（对应 AgentService.AgentInput）。"""

    agent_type: str = Field(
        ...,
        description="Agent 标识",
        examples=["skill", "coach", "reflection", "orchestrator"],
    )
    user_context: Dict[str, Any] = Field(
        default_factory=dict, description="用户/业务上下文（画像、测评、任务、学习数据等）"
    )
    retrieved_docs: List[Dict[str, Any]] = Field(
        default_factory=list, description="检索命中的知识片段 / 可选资源 / 错题要点"
    )
    history: List[Dict[str, Any]] = Field(
        default_factory=list, description="最近的对话历史 [{role, content}]"
    )
    fallback: Optional[Dict[str, Any]] = Field(
        default=None, description="规则引擎降级结果（LLM 不可用时直接返回）"
    )
    temperature: Optional[float] = Field(
        default=None, ge=0.0, le=2.0, description="采样温度(默认取 Agent 定义)"
    )
    max_tokens: Optional[int] = Field(
        default=None, ge=16, le=8192, description="最大输出 token(默认取 Agent 定义)"
    )


class AgentRunOut(BaseModel):
    """统一 Agent 出参（对应 AgentService.AgentResult）。"""

    agent_type: str
    ok: bool
    data: Optional[Dict[str, Any]] = None
    error: str = ""
    note: str = ""
    degraded: bool = False


class AgentInfoOut(BaseModel):
    """Agent 清单条目。"""

    name: str
    role: str
    description: str = ""