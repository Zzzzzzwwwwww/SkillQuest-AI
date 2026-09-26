"""
SkillQuest AI 统一 AgentService —— 华为云大模型多智能体调用服务

统一入口，接收统一的输入并返回统一的结构化 JSON 结果：

    payload = {
        "agent_type":    career|skill|learning|tutor|assessment|coach|reflection|orchestrator,
        "user_context":  { 用户画像 / 测评结果 / 任务 / 学习数据 等业务上下文 },
        "retrieved_docs": [ { 检索命中的知识片段 / 可选资源 / 错题要点 } ],
        "history":       [ { "role": ..., "content": ... } ] 最近的对话历史,
        "fallback":      { 规则引擎算好的降级结果（未配置模型/调用失败时返回） },
    }

流程：
  1. 按 agent_type 从 AGENT_REGISTRY 取 AgentSpec（系统提示词 + JSON Schema 约束）；
  2. 把 user_context / retrieved_docs / history 拼装为结构化 user_prompt；
  3. 调用 `LLMService.chat_json` 强制模型返回纯 JSON 并解析为 dict；
  4. 返回统一 AgentResult：{agent_type, ok, data, error, note, degraded}。

原则（第 1 条）：能规则算的不用大模型 —— 各 Agent 系统提示词明令禁止
参与评分/掌握度/XP 等数值计算；因此本服务只负责"生成、分析、解释、推荐"类输出。
"""

import json
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from app.agents.prompts import AGENT_REGISTRY, AGENT_TASKS, AgentSpec
from app.services.llm import (
    LLMNotConfiguredError,
    LLMResponseError,
    LLMService,
    llm_service,
)

# 上下文裁剪上限（控制 token 成本，避免历史/文档过长）
_HISTORY_MAX = 6        # 最多取最近 N 轮
_HISTORY_CHAR = 300     # 每条对话内容最长字符
_DOCS_MAX = 8           # 最多取 N 条检索资料
_DOC_CONTENT_CHAR = 500  # 每条资料正文最长字符

# 资料正文可能使用的字段名（任一命中即裁剪）
_DOC_BODY_FIELDS = ("content", "evidence", "context", "text", "原文")


class AgentInput(BaseModel):
    """统一 Agent 入参。"""

    agent_type: str = Field(
        ...,
        description="Agent 标识：career/skill/learning/tutor/assessment/coach/reflection/orchestrator",
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
        default=None, description="采样温度，默认取 AgentSpec.default_temperature"
    )
    max_tokens: Optional[int] = Field(
        default=None, description="最大输出 token，默认取 AgentSpec.default_max_tokens"
    )
    max_retries: int = Field(default=2, description="JSON 解析失败最大重试次数")


class AgentResult(BaseModel):
    """统一 Agent 出参。"""

    agent_type: str = Field(..., description="Agent 标识")
    ok: bool = Field(..., description="是否成功产出结构化数据")
    data: Optional[Dict[str, Any]] = Field(default=None, description="解析后的 JSON 结果")
    error: str = Field(default="", description="错误信息（ok=False/degraded 时给出原因）")
    note: str = Field(default="", description="说明（降级来源等）")
    degraded: bool = Field(
        default=False, description="是否为降级结果（未配置模型 / 调用失败走规则 fallback）"
    )


# --------------------------------------------------------------------- #
# 上下文剪裁与 user_prompt 拼装
# --------------------------------------------------------------------- #
def _simplify_history(items: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """精简历史：只取最近 N 轮，每条仅保留 role + 截断的 content。"""
    out: List[Dict[str, str]] = []
    for it in items[-_HISTORY_MAX:]:
        if isinstance(it, dict):
            role = str(it.get("role") or it.get("speaker") or "")
            content = str(it.get("content") or it.get("text") or "")
            out.append({"role": role[:20], "content": content[:_HISTORY_CHAR]})
        else:
            out.append({"role": "message", "content": str(it)[:_HISTORY_CHAR]})
    return out


def _simplify_docs(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """精简检索资料：最多 N 条，正文超长字段截断。"""
    out: List[Dict[str, Any]] = []
    for d in docs[:_DOCS_MAX]:
        if not isinstance(d, dict):
            out.append({"content": str(d)[:_DOC_CONTENT_CHAR]})
            continue
        cp: Dict[str, Any] = dict(d)
        for key in _DOC_BODY_FIELDS:
            if key in cp and isinstance(cp[key], str) and len(cp[key]) > _DOC_CONTENT_CHAR:
                cp[key] = cp[key][:_DOC_CONTENT_CHAR] + "...(已截断)"
        out.append(cp)
    return out


def _task_for(spec: AgentSpec) -> str:
    """取该 Agent 的任务指令（AGENT_TASKS 优先，description 兜底）。"""
    return AGENT_TASKS.get(spec.name) or spec.description or f"执行「{spec.role}」任务。"


def build_user_prompt(spec: AgentSpec, inp: AgentInput) -> str:
    """把统一入参拼装为结构化的 user_prompt。"""
    sections = [
        f"【任务】\n{_task_for(spec)}",
        "【用户上下文】\n" + json.dumps(inp.user_context, ensure_ascii=False),
    ]
    if inp.retrieved_docs:
        sections.append(
            "【检索资料】\n"
            + json.dumps(_simplify_docs(inp.retrieved_docs), ensure_ascii=False)
        )
    else:
        sections.append("【检索资料】\n（无）")
    if inp.history:
        sections.append(
            "【对话历史】\n" + json.dumps(_simplify_history(inp.history), ensure_ascii=False)
        )
    else:
        sections.append("【对话历史】\n（无）")
    sections.append("仅输出符合系统提示中 JSON Schema 的纯 JSON，不要输出额外说明。")
    return "\n\n".join(sections)


# --------------------------------------------------------------------- #
# AgentService
# --------------------------------------------------------------------- #
class AgentService:
    """统一多智能体调用服务（华为云大模型）。"""

    def __init__(self, llm: Optional[LLMService] = None) -> None:
        self._llm = llm

    @property
    def llm(self) -> LLMService:
        if self._llm is None:
            self._llm = llm_service
        return self._llm

    def resolve_spec(self, agent_type: str) -> Optional[AgentSpec]:
        """按名称解析 Agent 定义；未知名称返回 None。"""
        return AGENT_REGISTRY.get(agent_type)

    def available_agents(self) -> List[Dict[str, str]]:
        """返回可调用的 Agent 清单（供前端/调试展示）。"""
        return [
            {
                "name": spec.name,
                "role": spec.role,
                "description": spec.description or spec.role,
            }
            for spec in AGENT_REGISTRY.values()
        ]

    @staticmethod
    def _degrade(
        spec: AgentSpec,
        inp: AgentInput,
        reason: str,
    ) -> AgentResult:
        """LLM 不可用/失败时的统一降级。"""
        note = (
            f"LLM 未接入或调用失败（{reason}），已改用业务规则结果。"
            if inp.fallback
            else "LLM 未接入或调用失败（{}），业务方需提供规则降级结果。".format(reason)
        )
        return AgentResult(
            agent_type=spec.name,
            ok=inp.fallback is not None,
            data=inp.fallback,
            error=reason,
            note=note,
            degraded=True,
        )

    async def run(self, payload: Union[AgentInput, Dict[str, Any]]) -> AgentResult:
        """执行 Agent：选择提示词 → 拼装上下文 → 调用大模型 → 解析 JSON。

        Args:
            payload: 统一入参（AgentInput 实例或等价的 dict）。

        Returns:
            统一 AgentResult；未配置模型或调用失败时自动降级，
            优先使用入参中的 fallback 规则结果。
        """
        inp = payload if isinstance(payload, AgentInput) else AgentInput(**payload)
        spec = self.resolve_spec(inp.agent_type)
        if spec is None:
            return AgentResult(
                agent_type=inp.agent_type,
                ok=False,
                error=f"未注册的 Agent: {inp.agent_type}。可用: {', '.join(AGENT_REGISTRY)}",
                degraded=True,
            )
        if not self.llm.is_configured:
            return self._degrade(spec, inp, "华为云大模型未配置 HUAWEI_LLM_API_KEY/HUAWEI_LLM_ENDPOINT")

        user_prompt = build_user_prompt(spec, inp)
        try:
            data = await self.llm.chat_json(
                system_prompt=spec.system_prompt,
                user_prompt=user_prompt,
                schema_hint=spec.json_schema,
                temperature=inp.temperature if inp.temperature is not None else spec.default_temperature,
                max_tokens=inp.max_tokens if inp.max_tokens is not None else spec.default_max_tokens,
                max_retries=inp.max_retries,
            )
            return AgentResult(
                agent_type=spec.name,
                ok=True,
                data=data,
                note="模型输出已解析为 JSON",
                degraded=False,
            )
        except (LLMNotConfiguredError, LLMResponseError) as exc:
            return self._degrade(spec, inp, str(exc))
        except Exception as exc:  # noqa: BLE001  网络/编码等任何异常统一降级
            return self._degrade(spec, inp, str(exc))

    async def stream(
        self, payload: Union[AgentInput, Dict[str, Any]]
    ) -> AsyncIterator[str]:
        """流式执行 Agent（如 Tutor 答疑），按文本块逐步产出。

        与 run() 共用统一的选择提示词/拼装上下文逻辑；差异仅在于
        调用 `LLMService.chat_stream` 而非 `chat_json`（不做 JSON 解析，
        输出原样透传，适合 SSE 逐字渲染场景）。

        未配置大模型或 Agent 不存在时直接结束（空流），调用方应自行降级。

        Args:
            payload: 统一入参（AgentInput 实例或等价的 dict）。

        Yields:
            LLM 流式输出的文本片段。
        """
        inp = payload if isinstance(payload, AgentInput) else AgentInput(**payload)
        spec = self.resolve_spec(inp.agent_type)
        if spec is None or not self.llm.is_configured:
            return
        user_prompt = build_user_prompt(spec, inp)
        try:
            async for piece in self.llm.chat_stream(
                system_prompt=spec.system_prompt,
                user_prompt=user_prompt,
                temperature=(
                    inp.temperature if inp.temperature is not None else spec.default_temperature
                ),
                max_tokens=(
                    inp.max_tokens if inp.max_tokens is not None else spec.default_max_tokens
                ),
            ):
                yield piece
        except Exception:  # noqa: BLE001  流式失败由调用方降级
            return


# 全局单例：业务模块直接复用
agent_service = AgentService()