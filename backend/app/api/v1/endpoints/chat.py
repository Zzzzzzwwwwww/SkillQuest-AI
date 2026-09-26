"""
SkillQuest AI 智能答疑（RAG）接口（模块6）

  - POST /chat/session            创建答疑会话
  - POST /chat/message            发送消息（SSE 流式：delta/answer/meta/done）
  - GET  /chat/history            会话历史 + 指定会话消息
  - POST /knowledge/upload        上传文档（切分+向量化入库）
  - GET  /knowledge/search        知识库相似检索

RAG 流程：上传 → 切分 → Embedding(模型/规则) → 向量库 → 提问时检索 →
          规则重排 → 组装 Prompt(Tutor) → 华为云大模型流式生成 →
          答案 + 引用来源 + 关联知识点 + 推荐练习，全程落库。
"""

import json
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.response import success
from app.core.security import get_current_user
from app.db.session import get_db
from app.models import LearningResource, SkillNode
from app.models.user import User
from app.models.chat import (
    ROLE_ASSISTANT,
    ROLE_USER,
    ChatMessage,
    ChatSession,
    KnowledgeChunk,
    KnowledgeDocument,
    QaLog,
)
from app.schemas.chat import (
    ChatHistoryOut,
    ChatMessageIn,
    ChatSessionCreate,
    KnowledgeSearchOut,
    KnowledgeUploadIn,
    KnowledgeUploadOut,
)
from app.services.agent_service import AgentInput, agent_service
from app.services.rag import (
    build_learning_context,
    embedding_service,
    index_document,
    map_related_skills,
    recommend_practices,
    retrieve_chunks,
)

chat_router = APIRouter(prefix="/chat", tags=["chat"])
knowledge_router = APIRouter(prefix="/knowledge", tags=["knowledge"])


# -------------------------------------------------------------------- #
# SSE 工具
# -------------------------------------------------------------------- #
def _sse(entity: str, data: Any) -> bytes:
    """序列化一条 SSE 事件：event: <entity>\ndata: <json>\n\n。"""
    return f"event: {entity}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


def _chunk_answer(text: str, size: int = 8) -> List[str]:
    """把答案切分为小片段用于 SSE 增量推送（模拟流式，按字符块）。"""
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]


async def _answer_flow(
    user_id: int,
    session_id: int,
    question: str,
) -> AsyncIterator[bytes]:
    """统一答案生成流：检索 → Prompt → LLM(流式/降级) → 引用落库。

    注意：SSE 生成器在请求依赖关闭后才被迭代，因此内部自建 Session，
    不依赖 FastAPI 请求级的 get_db。
    """
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        session = db.get(ChatSession, session_id)
        if session is None:
            return
        user = db.get(User, user_id)
        if user is None:
            return

        hits = retrieve_chunks(db, question)
        related_skills = map_related_skills(db, hits)
        practice = recommend_practices(
            db, related_skills[0]["skill_node_id"] if related_skills else None
        )
        learning_context = build_learning_context(db, user_id)

        # 最近对话（组装 prompt 用）
        history: List[Dict[str, str]] = []
        history_rows = db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.id.asc())
        ).all()[-6:]
        for m in history_rows:
            history.append({"role": m.role, "content": m.content[:200]})

        # ---------- 生成答案 ----------
        answer_text = ""
        references: List[Dict[str, Any]] = []
        sufficient = bool(hits)

        # 统一 AgentService 通道：Tutor Agent 流式答疑（未配置/未知 Agent 返回空流）
        tutor_input = AgentInput(
            agent_type="tutor",
            user_context={
                "question": question,
                "learning_context": learning_context,
            },
            retrieved_docs=[
                {
                    "doc_title": h["doc_title"],
                    "source": h.get("source", "") or "",
                    "content": h["content"],
                    "score": h.get("score", 0),
                }
                for h in hits[:8]
            ],
            history=history,
            temperature=0.3,
            max_tokens=1024,
        )
        streamed = False
        try:
            async for piece in agent_service.stream(tutor_input):
                streamed = True
                answer_text += piece
                yield _sse("delta", {"token": piece})
        except Exception:
            streamed = False
        if not streamed:
            # 未配置大模型 / 调用失败 → 规则降级为证据摘要
            answer_text = _fallback_summary(hits)
            for piece in _chunk_answer(answer_text):
                yield _sse("delta", {"token": piece})

        # 引用来源：由检索命中结构化生成（答案必带引用）
        if hits:
            references = [
                {
                    "chunk_id": h["chunk_id"],
                    "doc_title": h["doc_title"],
                    "source": h["source"],
                    "score": h["score"],
                    "evidence": h["content"][:200],
                    "url": "",
                }
                for h in hits[:3]
            ]

        # ---------- 落库 ----------
        assistant_msg = ChatMessage(
            session_id=session.id,
            role=ROLE_ASSISTANT,
            content=answer_text,
            references_json=references,
        )
        db.add(assistant_msg)
        db.add(
            QaLog(
                user_id=user.id,
                question=question,
                answer=answer_text,
                skill_node_id=(
                    related_skills[0]["skill_node_id"] if related_skills else None
                ),
            )
        )
        # 答疑 XP（规则：一次答疑 +5），计入 XP 流水与档案
        from app.services.gamification import record_action_xp

        record_action_xp(db, user.id, "question", "AI 导师答疑")
        db.commit()
        db.refresh(assistant_msg)

        yield _sse("answer", {"answer": answer_text})
        yield _sse("references", {"references": references,
                                  "sufficient": sufficient})
        yield _sse("knowledge", {"related_skills": related_skills})
        yield _sse("practice", {"practice": practice[:3]})
        yield _sse("done", {"message_id": assistant_msg.id, "session_id": session.id})
    finally:
        db.close()


def _fallback_summary(hits: List[Dict[str, Any]]) -> str:
    """未配置 LLM 时的规则降级答案（引用检索证据/明确说明未命中）。"""
    if not hits:
        return (
            "很抱歉，知识库中暂未检索到与你的问题直接相关的内容。"
            "可以尝试：1) 换一种关键词或更具体的问法；"
            "2) 先在「冒险地图」或「技能图谱」中定位相关技能；"
            "3) 联系管理员上传更多知识文档。"
        )
    lines = [
        "根据知识库中的已有文档，为你整理如下要点（以下内容依据检索证据归纳）："
    ]
    for h in hits[:3]:
        lines.append(f"- 《{h['doc_title']}》{h['source'] or ''}：{h['content'][:120]}")
    lines.append("（当前为规则问答模式；配置华为云大模型后，将获得更完整的解释。）")
    return "\n".join(lines)


# -------------------------------------------------------------------- #
# 会话管理
# -------------------------------------------------------------------- #
@chat_router.post(
    "/session",
    summary="创建答疑会话",
)
def create_session(
    payload: ChatSessionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """创建会话；标题缺省时自动生成。"""
    title = (payload.title or "").strip() or "新对话"
    session = ChatSession(user_id=user.id, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return success({"id": session.id, "title": session.title,
                    "created_at": session.created_at.isoformat()})


@chat_router.get(
    "/history",
    summary="会话历史与消息",
)
def get_chat_history(
    session_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """无 session_id 返回会话列表；有则返回该会话消息。"""
    if session_id:
        session = db.get(ChatSession, session_id)
        if session is None or session.user_id != user.id:
            raise HTTPException(status_code=404, detail="会话不存在")
        msgs = db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.id.asc())
        ).all()
        return success(
            ChatHistoryOut(
                sessions=[],
                messages=[
                    {
                        "id": m.id,
                        "role": m.role,
                        "content": m.content,
                        "references": m.references_json or [],
                        "created_at": (
                            m.created_at.isoformat() if m.created_at else None
                        ),
                    }
                    for m in msgs
                ],
            ).model_dump()
        )

    sessions = db.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.id.desc())
        .limit(50)
    ).all()
    out_sessions: List[Dict[str, Any]] = []
    for s in sessions:
        last = db.scalar(
            select(ChatMessage)
            .where(ChatMessage.session_id == s.id)
            .order_by(ChatMessage.id.desc())
            .limit(1)
        )
        cnt = db.scalar(
            select(func.count(ChatMessage.id)).where(
                ChatMessage.session_id == s.id
            )
        )
        out_sessions.append(
            {
                "id": s.id,
                "title": s.title,
                "message_count": int(cnt or 0),
                "last_message": last.content[:60] if last else None,
                "created_at": (
                    s.created_at.isoformat() if s.created_at else None
                ),
            }
        )
    # 校验出参（示范 schema 校验；实际直接返回 dict）
    return success(ChatHistoryOut(sessions=out_sessions, messages=[]).model_dump())


# -------------------------------------------------------------------- #
# 发送消息（SSE 流式）
# -------------------------------------------------------------------- #
@chat_router.post(
    "/message",
    summary="发送消息（SSE 流式返回）",
    description="返回 text/event-stream；事件：delta(增量)/meta(answer/references/knowledge/practice)/done。",
)
async def send_message(
    payload: ChatMessageIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from fastapi.responses import StreamingResponse

    session = db.get(ChatSession, payload.session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")

    question = payload.content.strip()
    if not question:
        raise HTTPException(status_code=422, detail="问题不能为空")

    # 用户消息落库
    db.add(
        ChatMessage(
            session_id=session.id, role=ROLE_USER, content=question,
            references_json=[],
        )
    )
    db.commit()

    # 注意：SSE 生成器在依赖关闭后才迭代，这里提前捕获所需值
    uid = user.id
    sid = session.id
    return StreamingResponse(
        _answer_flow(uid, sid, question),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# -------------------------------------------------------------------- #
# 知识库：上传 / 检索
# -------------------------------------------------------------------- #
@knowledge_router.post(
    "/upload",
    summary="上传知识文档（切分+向量化）",
)
async def upload_knowledge(
    payload: KnowledgeUploadIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """接收纯文本文档，切分 + Embedding 入库（rule/model 自动选择）。"""
    if not payload.content.strip():
        raise HTTPException(status_code=422, detail="文档内容不能为空")
    doc = await index_document(
        db,
        title=payload.title,
        content=payload.content,
        source=payload.source or "",
        file_url=payload.file_url,
        skill_node_id=payload.skill_node_id,
    )
    chunk_count = db.scalar(
        select(func.count(KnowledgeChunk.id)).where(
            KnowledgeChunk.document_id == doc.id
        )
    )
    return success(
        KnowledgeUploadOut(
            document_id=doc.id,
            title=doc.title,
            status=doc.status,
            chunk_count=int(chunk_count or 0),
            embedding_mode=doc.embedding_mode,
        ).model_dump()
    )


@knowledge_router.get(
    "/search",
    summary="知识库相似检索",
)
def search_knowledge(
    q: str = "",
    top_k: int = 6,
    document_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """规则检索：query 向量化 + 关键词重排。返回 hits（含文档标题/分数/原文）。"""
    hits = retrieve_chunks(db, q, top_k=top_k, document_id=document_id)
    total = db.scalar(select(func.count(KnowledgeDocument.id)))
    return success(
        KnowledgeSearchOut(
            query=q,
            hits=hits,
            embedding_mode=embedding_service.mode,
            total_documents=int(total or 0),
        ).model_dump()
    )


# -------------------------------------------------------------------- #
# 业务闭环5：弱点诊断推送 AI 导师
# -------------------------------------------------------------------- #
@chat_router.get(
    "/weaknesses",
    summary="弱点诊断列表（AI 导师推送）",
    description="返回阶段测评弱点诊断中待处理(未治愈)的条目，供导师页面主动展示与引导。",
)
def list_weakness_diagnostics(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    from app.models.business_loop import DIAG_NEW, WeaknessDiagnostic

    rows = db.scalars(
        select(WeaknessDiagnostic)
        .where(
            WeaknessDiagnostic.user_id == user.id,
            WeaknessDiagnostic.status.in_([DIAG_NEW, "notified"]),
        )
        .order_by(WeaknessDiagnostic.id.desc())
        .limit(10)
    ).all()
    return success([
        {
            "id": d.id,
            "knowledge_point_id": d.knowledge_point_id,
            "kp_name": d.kp_name,
            "domain": d.domain,
            "mastery_score": d.mastery_score,
            "diagnosis": d.diagnosis,
            "created_at": d.created_at.isoformat() if d.created_at else "",
        }
        for d in rows
    ])