"""
SkillQuest AI 统一多智能体接口（AgentService 接入层）

  - GET  /agents         Agent 清单（供前端/调试展示）
  - POST /agents/run     统一调用：任意 Agent → 结构化 JSON 结果（降级友好）
  - POST /agents/stream  SSE 流式（Tutor/Coach 等逐字渲染场景）

设计原则（第 1 条）：能规则算的不用大模型 —— 各 Agent 提示词明令禁止
参与算分/掌握度/XP 等数值计算；未配置大模型或调用失败时，接口返回
degraded 标记与业务侧 fallback（若有），不中断业务。
"""

import json
from typing import Any, AsyncIterator, Dict, List

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.response import success
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.agent import AgentInfoOut, AgentRunIn, AgentRunOut
from app.schemas.common import ApiResponse
from app.services.agent_service import AgentInput, agent_service

router = APIRouter(prefix="/agents", tags=["agents"])


def _sse(entity: str, data: Any) -> bytes:
    """序列化一条 SSE 事件：event: <entity>\ndata: <json>\n\n。"""
    return f"event: {entity}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


@router.get(
    "",
    response_model=ApiResponse[List[AgentInfoOut]],
    summary="Agent 清单",
    description="返回全部可调用的多智能体定义（名称/角色/说明），供前端与调试展示。",
)
def list_agents(
    user: User = Depends(get_current_user),
) -> dict:
    """返回统一 AgentService 中注册的全部 Agent。"""
    return success(agent_service.available_agents())


@router.post(
    "/run",
    response_model=ApiResponse[AgentRunOut],
    summary="统一调用 Agent",
    description=(
        "按 agent_type 选择系统提示词，拼装上下文后调用华为云大模型，"
        "返回结构化 JSON；未配置模型/Agent 不存在/调用失败时降级（degraded）。"
    ),
)
async def run_agent(
    payload: AgentRunIn,
    user: User = Depends(get_current_user),
) -> dict:
    """统一 Agent 入口：一次调用一个 Agent，返回统一 AgentRunOut。"""
    result = await agent_service.run(
        AgentInput(
            agent_type=payload.agent_type,
            user_context=payload.user_context,
            retrieved_docs=payload.retrieved_docs,
            history=payload.history,
            fallback=payload.fallback,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )
    )
    return success(AgentRunOut(**result.model_dump()).model_dump())


@router.post(
    "/stream",
    summary="SSE 流式调用 Agent",
    description=(
        "流式逐字输出（text/event-stream）；未配置大模型或 Agent 不存在时"
        "直接返回空流，调用方按规则降级。事件：delta(文本块)/done。"
    ),
)
async def stream_agent(
    payload: AgentRunIn,
    user: User = Depends(get_current_user),
):
    """SSE 流式 Agent 通道（复用统一提示词/上下文拼装）。"""
    agent_input = AgentInput(
        agent_type=payload.agent_type,
        user_context=payload.user_context,
        retrieved_docs=payload.retrieved_docs,
        history=payload.history,
        fallback=payload.fallback,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )

    async def _gen() -> AsyncIterator[bytes]:
        try:
            async for piece in agent_service.stream(agent_input):
                yield _sse("delta", {"token": piece})
        except Exception:  # noqa: BLE001  流式失败由调用方降级
            pass
        yield _sse("done", {"agent_type": payload.agent_type})

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )