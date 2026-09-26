"""add chat rag module tables

模块6：智能答疑（RAG）—— 新增 5 张表：
  1. chat_sessions            答疑会话
  2. chat_messages            会话消息（含引用来源 references_json）
  3. knowledge_documents      知识文档（上传/RAG 检索源）
  4. knowledge_chunks         文档分块（向量 embedding + 元数据）
  5. qa_logs                  问答记录（问题/答案/关联技能节点）

Revision ID: 20260106_0006
Revises: 20260105_0005
Create Date: 2026-01-06 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260106_0006"
down_revision: str = "20260105_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级：新建答疑 RAG 5 张表。"""
    # ---------- chat_sessions ----------
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("title", sa.String(length=128), nullable=False, comment="会话标题"),
        sa.Column("created_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"), nullable=False, comment="更新时间"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="答疑会话表",
    )
    op.create_index("ix_chat_sessions_user", "chat_sessions", ["user_id", "created_at"])

    # ---------- chat_messages ----------
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("session_id", sa.BigInteger(), nullable=False, comment="会话ID"),
        sa.Column("role", sa.String(length=16), nullable=False, comment="消息角色 user/assistant"),
        sa.Column("content", sa.Text(), nullable=False, comment="消息内容"),
        sa.Column("references_json", sa.JSON(), nullable=True, comment="引用来源数组"),
        sa.Column("created_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False, comment="创建时间"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="会话消息表",
    )
    op.create_index("ix_chat_messages_session", "chat_messages", ["session_id", "created_at"])

    # ---------- knowledge_documents ----------
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("title", sa.String(length=256), nullable=False, comment="文档标题"),
        sa.Column("source", sa.String(length=256), server_default="", nullable=False, comment="来源(如课程名/平台)"),
        sa.Column("file_url", sa.String(length=512), nullable=True, comment="原始文件链接"),
        sa.Column("status", sa.String(length=16), server_default="ready", nullable=False, comment="状态 pending/ready/failed"),
        sa.Column("embedding_mode", sa.String(length=16), server_default="rule", nullable=False, comment="实际使用的向量模式 rule/model"),
        sa.Column("created_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        comment="知识文档表",
    )
    op.create_index("ix_knowledge_docs_status", "knowledge_documents", ["status"])

    # ---------- knowledge_chunks ----------
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("document_id", sa.BigInteger(), nullable=False, comment="所属文档ID"),
        sa.Column("content", sa.Text(), nullable=False, comment="分块文本"),
        sa.Column("embedding", sa.JSON(), nullable=True, comment="向量(JSON数组)"),
        sa.Column("metadata_json", sa.JSON(), nullable=True, comment="元数据(文档标题/来源/顺序等)"),
        sa.Column("created_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False, comment="创建时间"),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="知识分块表",
    )
    op.create_index("ix_knowledge_chunks_doc", "knowledge_chunks", ["document_id"])

    # ---------- qa_logs ----------
    op.create_table(
        "qa_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("question", sa.Text(), nullable=False, comment="用户问题"),
        sa.Column("answer", sa.Text(), nullable=False, comment="助手回答"),
        sa.Column("skill_node_id", sa.BigInteger(), nullable=True, comment="关联技能节点ID(检索命中最相关)"),
        sa.Column("created_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False, comment="创建时间"),
        sa.ForeignKeyConstraint(["skill_node_id"], ["skill_nodes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="问答记录表",
    )
    op.create_index("ix_qa_logs_user", "qa_logs", ["user_id", "created_at"])


def downgrade() -> None:
    """回滚：删除答疑 RAG 5 张表。"""
    op.drop_index("ix_qa_logs_user", table_name="qa_logs")
    op.drop_table("qa_logs")
    op.drop_index("ix_knowledge_chunks_doc", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index("ix_knowledge_docs_status", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
    op.drop_index("ix_chat_messages_session", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_user", table_name="chat_sessions")
    op.drop_table("chat_sessions")