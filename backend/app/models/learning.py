"""
SkillQuest AI 学习档案与学习轨迹模型

  - learning_archives：用户的成长档案（一个用户可有多份历史档案，取最新一份为当前）
  - learning_records：学习轨迹流水（测评、课程、练习、阅读等行为打点，支持断点续学）
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# 学习记录模块类型
MODULE_ASSESSMENT = "assessment"   # 测评
MODULE_COURSE = "course"           # 课程
MODULE_EXERCISE = "exercise"       # 练习
MODULE_READ = "reading"            # 阅读
MODULE_TUTOR = "tutor"             # AI导师
MODULE_BOSS = "boss"               # Boss挑战

# 学习记录动作类型
ACTION_START = "start"             # 开始（断点续学续播点）
ACTION_FINISH = "finish"           # 完成
ACTION_SUBMIT = "submit"           # 提交
ACTION_PROGRESS = "progress"       # 进度更新


class LearningArchive(Base, TimestampMixin):
    """学习档案：归档目标岗位、等级、XP 快照。"""

    __tablename__ = "learning_archives"
    __table_args__ = {"comment": "学习档案表"}

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="用户ID",
    )
    archive_name: Mapped[str] = mapped_column(
        String(64), default="我的成长档案", nullable=False, comment="档案名称"
    )
    target_job: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, default=None, comment="目标岗位"
    )
    current_level: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, comment="当前等级"
    )
    total_xp: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="累计XP"
    )


class LearningRecord(Base):
    """学习轨迹流水：一条记录一次用户行为。"""

    __tablename__ = "learning_records"
    __table_args__ = (
        Index("ix_records_user_module", "user_id", "module_type"),
        Index("ix_records_user_created", "user_id", "created_at"),
        {"comment": "学习轨迹表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="用户ID",
    )
    module_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="模块类型 assessment/course/exercise/..."
    )
    action_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="动作 start/finish/submit/progress"
    )
    target_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, default=None, comment="目标对象ID(如题目/课程/试卷)"
    )
    duration: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="时长(秒)"
    )
    result: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, default=None, comment="结果快照(得分/正确率等, JSON)"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False, comment="发生时间"
    )