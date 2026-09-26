"""
SkillQuest AI 个性化导学模型（模块5）

表结构：
  - learning_paths              学习路径（一个用户一条进行中的路径）
  - learning_path_nodes         路径节点（青铜→白银→黄金→铂金→钻石→王者）
  - learning_resources          学习资源库（视频/课程/文章/练习）
  - learning_progress           节点学习进度（含断点位置 last_position）
  - resource_recommendations    资源推荐记录（规则评分 + 推荐理由）
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# 路径状态
PATH_ACTIVE = "active"      # 进行中
PATH_COMPLETED = "completed"  # 已完成

# 节点掌握状态（游戏化闭环）
NODE_LOCKED = "locked"        # 锁定（前置未达）
NODE_UNLOCKED = "unlocked"    # 已解锁待开始
NODE_LEARNING = "learning"    # 学习中
NODE_COMPLETED = "completed"  # 已完成
NODE_MASTERED = "mastered"    # 已掌握（达到岗位要求）

# 段位（由低到高 6 段）
STAGES = ["bronze", "silver", "gold", "platinum", "diamond", "king"]
STAGE_LABELS = {
    "bronze": "青铜",
    "silver": "白银",
    "gold": "黄金",
    "platinum": "铂金",
    "diamond": "钻石",
    "king": "王者",
}

# 资源类型
RESOURCE_VIDEO = "video"    # 视频
RESOURCE_COURSE = "course"  # 课程
RESOURCE_ARTICLE = "article"  # 文章
RESOURCE_EXERCISE = "exercise"  # 练习


class LearningPath(Base, TimestampMixin):
    """学习路径：目标岗位 + 分段渐进。"""

    __tablename__ = "learning_paths"
    __table_args__ = (
        Index("ix_learning_paths_user_status", "user_id", "status"),
        {"comment": "学习路径表"},
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
    target_job: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="目标岗位名称"
    )
    path_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="路径名称"
    )
    status: Mapped[str] = mapped_column(
        String(16), default=PATH_ACTIVE, nullable=False, comment="状态 active/completed"
    )
    current_node_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("learning_path_nodes.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        comment="当前节点ID(断点续学指针)",
    )


class LearningPathNode(Base):
    """路径节点：一个技能/知识点在学习路径中的排布。"""

    __tablename__ = "learning_path_nodes"
    __table_args__ = (
        UniqueConstraint("path_id", "skill_node_id", name="uq_path_skill"),
        Index("ix_path_nodes_path_order", "path_id", "order_no"),
        {"comment": "学习路径节点表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    path_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("learning_paths.id", ondelete="CASCADE"),
        nullable=False,
        comment="路径ID",
    )
    skill_node_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skill_nodes.id", ondelete="CASCADE"),
        nullable=False,
        comment="技能节点ID",
    )
    stage: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="段位 bronze/silver/gold/platinum/diamond/king"
    )
    order_no: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="路径内序号(从1递增)"
    )
    status: Mapped[str] = mapped_column(
        String(16), default=NODE_LOCKED, nullable=False, comment="节点状态"
    )
    estimated_hours: Mapped[int] = mapped_column(
        Integer, default=6, nullable=False, comment="预计学习时长(小时)"
    )
    prerequisites_json: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, default=list, comment="前置技能名称数组"
    )


class LearningResource(Base):
    """学习资源库：挂到技能/知识点节点。"""

    __tablename__ = "learning_resources"
    __table_args__ = (
        Index("ix_learning_resources_skill", "skill_node_id"),
        {"comment": "学习资源表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    title: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="资源标题"
    )
    type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="类型 video/course/article/exercise"
    )
    url: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="资源链接"
    )
    skill_node_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skill_nodes.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联技能节点ID",
    )
    difficulty: Mapped[int] = mapped_column(
        Integer, default=2, nullable=False, comment="难度 1-5"
    )
    duration: Mapped[int] = mapped_column(
        Integer, default=60, nullable=False, comment="预计时长(分钟)"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None, comment="资源描述"
    )


class LearningProgress(Base):
    """节点学习进度（含断点续学位置）。"""

    __tablename__ = "learning_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "path_id", "node_id", name="uq_user_path_node"),
        Index("ix_learning_progress_user", "user_id"),
        {"comment": "学习进度表"},
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
    path_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("learning_paths.id", ondelete="CASCADE"),
        nullable=False,
        comment="路径ID",
    )
    node_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("learning_path_nodes.id", ondelete="CASCADE"),
        nullable=False,
        comment="路径节点ID",
    )
    progress_percent: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="进度百分比 0-100"
    )
    last_position: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True, default=None, comment="断点位置(章节/页码/时间)"
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="更新时间",
    )


class ResourceRecommendation(Base):
    """资源推荐记录：rule 评分 + 推荐理由（持久化，供断点续学/复盘复用）。"""

    __tablename__ = "resource_recommendations"
    __table_args__ = (
        Index("ix_resource_rec_user", "user_id"),
        {"comment": "资源推荐记录表"},
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
    resource_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("learning_resources.id", ondelete="CASCADE"),
        nullable=False,
        comment="资源ID",
    )
    reason: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="推荐理由"
    )
    score: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="推荐评分 0-100"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False, comment="推荐时间"
    )