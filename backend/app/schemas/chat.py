"""
SkillQuest AI 智能答疑（RAG）Schema（模块6）。

约定：chat/message 接口返回 text/event-stream（SSE），
其余接口遵循统一 {code, message, data} 结构。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# -------------------------------------------------------------------- #
# 会话
# -------------------------------------------------------------------- #
class ChatSessionCreate(BaseModel):
    """创建会话入参。"""

    title: Optional[str] = Field(
        None, max_length=128, description="会话标题(缺省自动生成)"
    )


class ChatMessageOut(BaseModel):
    """历史消息。"""

    id: int
    role: str
    content: str
    references: List[Dict[str, Any]] = []
    created_at: Optional[str] = None


class ChatSessionOut(BaseModel):
    """会话（含最后一条消息预览）。"""

    id: int
    title: str
    message_count: int = 0
    last_message: Optional[str] = None
    created_at: Optional[str] = None


class ChatHistoryOut(BaseModel):
    """会话历史 + 消息列表。"""

    sessions: List[ChatSessionOut] = []
    messages: List[ChatMessageOut] = []


# -------------------------------------------------------------------- #
# 发送消息（SSE 事件负载定义，接口返回流式数据）
# -------------------------------------------------------------------- #
class ChatMessageIn(BaseModel):
    """发送消息入参。"""

    session_id: int = Field(..., description="会话ID")
    content: str = Field(..., max_length=2000, description="用户问题")


class SseDelta(BaseModel):
    """流式增量事件。"""

    event: str = "delta"
    token: str


class SseMeta(BaseModel):
    """流式元数据事件（引用/知识点/练习）。"""

    event: str
    data: Any


# -------------------------------------------------------------------- #
# 知识库
# -------------------------------------------------------------------- #
class KnowledgeUploadIn(BaseModel):
    """上传文档入参（文本方式）。"""

    title: str = Field(..., max_length=256, description="文档标题")
    content: str = Field(..., max_length=100_000, description="文档正文")
    source: Optional[str] = Field(None, max_length=256, description="来源")
    file_url: Optional[str] = Field(None, max_length=512, description="原始文件链接")
    skill_node_id: Optional[int] = Field(None, description="关联技能节点(用于练习推荐)")


class KnowledgeUploadOut(BaseModel):
    """上传结果。"""

    document_id: int
    title: str
    status: str
    chunk_count: int
    embedding_mode: str


class KnowledgeHitOut(BaseModel):
    """检索命中分块。"""

    chunk_id: int
    document_id: int
    doc_title: str
    source: str
    score: float
    content: str
    skill_node_id: Optional[int] = None


class KnowledgeSearchOut(BaseModel):
    """检索结果。"""

    query: str
    hits: List[KnowledgeHitOut] = []
    embedding_mode: str
    total_documents: int


# -------------------------------------------------------------------- #
# QA 记录
# -------------------------------------------------------------------- #
class QaLogOut(BaseModel):
    """问答记录（档案回溯用）。"""

    id: int
    question: str
    answer: str
    skill_node_id: Optional[int] = None
    created_at: Optional[str] = None