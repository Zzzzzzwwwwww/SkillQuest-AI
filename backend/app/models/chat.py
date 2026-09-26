"""
SkillQuest AI 智能答疑（RAG）模型（模块6）

表结构：
  - chat_sessions           对话会话（一个用户多个会话）
  - chat_messages           会话消息（用户/助手，含引用来源 references_json）
  - knowledge_documents     知识文档（上传、切分、索引入库）
  - knowledge_chunks        文档分块（文本 + 向量 embedding + 元数据）
  - qa_logs                 问答记录（问题/答案/关联技能节点）
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# 消息角色
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"

# 文档处理状态
DOC_PENDING = "pending"          # 待处理
DOC_PROCESSING = "processing"    # 处理中
DOC_READY = "ready"              # 已完成切分+向量化
DOC_FAILED = "failed"            # 处理失败

# 检索模式（Embedding 服务降级说明用）
EMBEDDING_MODE_RULE = "rule"        # 规则向量（未配置 Embedding 模型时降级）
EMBEDDING_MODE_MODEL = "model"      # 调用 Embedding 模型


class ChatSession(Base, TimestampMixin):
    """一次答疑会话（历史会话列表）。"""

    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_user", "user_id", "created_at"),
        {"comment": "答疑会话表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户ID",
    )
    title: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="会话标题"
    )


class ChatMessage(Base):
    """会话内一条消息（含引用来源 JSON）。"""

    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_session", "session_id", "created_at"),
        {"comment": "会话消息表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        comment="会话ID",
    )
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="消息角色 user/assistant"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="消息内容"
    )
    references_json: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, default=list, comment="引用来源数组"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, server_default=func.now(), nullable=False,
        comment="创建时间",
    )


class KnowledgeDocument(Base, TimestampMixin):
    """上传的知识文档（作为 RAG 检索源）。"""

    __tablename__ = "knowledge_documents"
    __table_args__ = (
        Index("ix_knowledge_docs_status", "status"),
        {"comment": "知识文档表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    title: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="文档标题"
    )
    source: Mapped[str] = mapped_column(
        String(256), default="", nullable=False, comment="来源(如课程名/平台)"
    )
    file_url: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True, default=None, comment="原始文件链接"
    )
    status: Mapped[str] = mapped_column(
        String(16), default=DOC_READY, nullable=False, comment="状态 pending/ready/failed"
    )
    embedding_mode: Mapped[str] = mapped_column(
        String(16), default=EMBEDDING_MODE_RULE, nullable=False,
        comment="实际使用的向量模式 rule/model",
    )


class KnowledgeChunk(Base):
    """文档切分后的知识块（含向量与元数据）。"""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index("ix_knowledge_chunks_doc", "document_id"),
        {"comment": "知识分块表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属文档ID",
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="分块文本"
    )
    embedding: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, default=None, comment="向量(JSON数组，维度由Embedding决定)"
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, default=dict, comment="元数据(文档标题/来源/顺序等)"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, server_default=func.now(), nullable=False,
        comment="创建时间",
    )


class QaLog(Base):
    """一次问答记录（用于学习档案/复盘追溯）。"""

    __tablename__ = "qa_logs"
    __table_args__ = (
        Index("ix_qa_logs_user", "user_id", "created_at"),
        {"comment": "问答记录表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户ID",
    )
    question: Mapped[str] = mapped_column(
        Text, nullable=False, comment="用户问题"
    )
    answer: Mapped[str] = mapped_column(
        Text, nullable=False, comment="助手回答"
    )
    skill_node_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("skill_nodes.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        comment="关联技能节点ID(检索命中最相关)",
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, server_default=func.now(), nullable=False,
        comment="创建时间",
    )

    def to_dict(self) -> dict[str, Any]:
        """规则序列化：供学习档案读取。"""
        return {
            "id": self.id,
            "question": self.question,
            "answer": self.answer,
            "skill_node_id": self.skill_node_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }