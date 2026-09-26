"""
SkillQuest AI 岗位技能图谱模型（模块4）

技能层级：岗位族(job_family) → 岗位(jobs) → 能力域(node_type=capability)
          → 技能(node_type=skill) → 知识点(node_type=knowledge)。

表结构：
  - jobs                  岗位（归属岗位族 job_family）
  - skill_nodes           技能节点树（parent_id 自引用，level 1/2/3）
  - job_skill_relations   岗位 ↔ 技能节点（重要度 + 岗位要求掌握度）
  - user_skill_status     用户掌握状态（mastered/learning/not_started + 掌握度）
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# 岗位状态
JOB_ACTIVE = "active"
JOB_OFFLINE = "offline"

# 技能节点类型（层级）
NODE_CAPABILITY = "capability"  # 能力域（level 1）
NODE_SKILL = "skill"            # 技能（level 2）
NODE_KNOWLEDGE = "knowledge"    # 知识点（level 3）

# 掌握状态
STATUS_MASTERED = "mastered"        # 已掌握
STATUS_LEARNING = "learning"        # 学习中
STATUS_NOT_STARTED = "not_started"  # 未掌握


class Job(Base, TimestampMixin):
    """岗位：技能图谱的根节点。"""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_family_status", "job_family", "status"),
        {"comment": "岗位表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    job_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="岗位名称"
    )
    job_family: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="岗位族"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None, comment="岗位描述"
    )
    industry: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, default=None, comment="所属行业"
    )
    status: Mapped[str] = mapped_column(
        String(16), default=JOB_ACTIVE, nullable=False, comment="状态 active/offline"
    )


class SkillNode(Base, TimestampMixin):
    """技能节点树：能力域 → 技能 → 知识点。"""

    __tablename__ = "skill_nodes"
    __table_args__ = (
        Index("ix_skill_nodes_parent", "parent_id"),
        Index("ix_skill_nodes_type_level", "node_type", "level"),
        {"comment": "技能节点表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="节点名称"
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("skill_nodes.id", ondelete="CASCADE"),
        nullable=True,
        default=None,
        comment="父节点ID(自引用)",
    )
    level: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, comment="层级 1能力域/2技能/3知识点"
    )
    node_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="节点类型 capability/skill/knowledge"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None, comment="节点描述"
    )
    importance: Mapped[int] = mapped_column(
        Integer, default=50, nullable=False, comment="重要度(0-100)"
    )
    prerequisites_json: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="前置知识/技能名称数组",
    )


class JobSkillRelation(Base):
    """岗位 ↔ 技能节点关系（多对多，带岗位要求）。"""

    __tablename__ = "job_skill_relations"
    __table_args__ = (
        UniqueConstraint("job_id", "skill_node_id", name="uq_job_skill"),
        Index("ix_relations_skill", "skill_node_id"),
        {"comment": "岗位技能关系表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    job_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="岗位ID",
    )
    skill_node_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skill_nodes.id", ondelete="CASCADE"),
        nullable=False,
        comment="技能节点ID",
    )
    importance: Mapped[int] = mapped_column(
        Integer, default=50, nullable=False, comment="对岗位的重要度(0-100)"
    )
    required_level: Mapped[int] = mapped_column(
        Integer, default=60, nullable=False, comment="岗位要求掌握度(0-100)"
    )


class UserSkillStatus(Base):
    """用户对技能节点的掌握状态。"""

    __tablename__ = "user_skill_status"
    __table_args__ = (
        UniqueConstraint("user_id", "skill_node_id", name="uq_user_skill"),
        Index("ix_user_skill_status_user", "user_id"),
        {"comment": "用户技能状态表"},
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
    skill_node_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skill_nodes.id", ondelete="CASCADE"),
        nullable=False,
        comment="技能节点ID",
    )
    status: Mapped[str] = mapped_column(
        String(16), default=STATUS_NOT_STARTED, nullable=False, comment="掌握状态"
    )
    mastery_score: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="掌握度(0-100)"
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="更新时间",
    )