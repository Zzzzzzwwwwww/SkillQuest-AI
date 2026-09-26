"""
SkillQuest AI 游戏化模型（模块9：成长激励体系）

  - achievements              成就定义（种子数据，condition_json 描述解锁规则）
  - user_achievements         用户已解锁成就
  - xp_logs                   XP 流水（每次获得 XP 落一条，action_type 分类）
  - pomodoro_sessions         番茄钟专注记录（25/40 分钟模式）

设计原则（第1条）：等级/段位/XP/连击/成就全部规则计算，无大模型参与。
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# --------------------------------------------------------------------- #
# XP 动作类型（谁给 XP，规则表在 services/gamification.py）
# --------------------------------------------------------------------- #
XP_ACTION_STUDY = "study"          # 完成学习任务（学习时长/课程进度）
XP_ACTION_TASK = "daily_task"      # 完成每日督导任务
XP_ACTION_PROJECT = "project"      # 完成项目
XP_ACTION_BOSS = "boss"            # Boss 挑战通过
XP_ACTION_QUESTION = "question"    # AI 导师答疑
XP_ACTION_POMODORO = "pomodoro"    # 番茄钟专注
XP_ACTION_WEAKNESS = "weakness"    # 攻克弱点诊断
XP_ACTION_ACHIEVEMENT = "achievement"  # 解锁成就奖励

# 番茄钟模式
POMODORO_FOCUS = "focus"           # 25 分钟专注
POMODORO_DEEP = "deep"             # 40 分钟深度专注


class Achievement(Base, TimestampMixin):
    """成就定义表（种子写入，可按 name 幂等 upsert）。"""

    __tablename__ = "achievements"
    __table_args__ = (Index("ix_achievements_name", "name"), {"comment": "成就定义表"})

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    name: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, comment="成就唯一标识"
    )
    title: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="成就名称（前端展示）"
    )
    description: Mapped[str] = mapped_column(
        String(256), default="", nullable=False, comment="成就描述"
    )
    icon: Mapped[str] = mapped_column(
        String(64), default="", nullable=False, comment="图标标识（前端映射）"
    )
    condition_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, default=None, comment="解锁条件（规则引擎读取）"
    )
    xp_reward: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="解锁奖励 XP"
    )
    hidden: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="是否隐藏（1=未解锁时不展示条件）"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="排序"
    )


class UserAchievement(Base):
    """用户已解锁成就。"""

    __tablename__ = "user_achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
        Index("ix_user_achievement_user", "user_id"),
        {"comment": "用户成就表"},
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
    achievement_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("achievements.id", ondelete="CASCADE"),
        nullable=False,
        comment="成就ID",
    )
    unlocked_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False, comment="解锁时间"
    )


class XpLog(Base):
    """XP 流水：每次获得 XP 落一条，支撑成长首页明细与连击统计。"""

    __tablename__ = "xp_logs"
    __table_args__ = (
        Index("ix_xp_logs_user_created", "user_id", "created_at"),
        Index("ix_xp_logs_user_action", "user_id", "action_type"),
        {"comment": "XP流水表"},
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
    action_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="动作类型 study/daily_task/project/boss/..."
    )
    xp_amount: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="本次获得 XP"
    )
    note: Mapped[str] = mapped_column(
        String(256), default="", nullable=False, comment="说明/来源"
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, default=None, comment="扩展信息（如目标ID）"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False, comment="获得时间"
    )


class PomodoroSession(Base, TimestampMixin):
    """番茄钟专注记录。"""

    __tablename__ = "pomodoro_sessions"
    __table_args__ = (
        Index("ix_pomodoro_user_created", "user_id", "created_at"),
        {"comment": "番茄钟记录表"},
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
    mode: Mapped[str] = mapped_column(
        String(16), default=POMODORO_FOCUS, nullable=False, comment="模式 focus/deep"
    )
    focus_minutes: Mapped[int] = mapped_column(
        Integer, default=25, nullable=False, comment="专注分钟数"
    )
    break_minutes: Mapped[int] = mapped_column(
        Integer, default=5, nullable=False, comment="休息分钟数"
    )
    rounds: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, comment="完成轮数"
    )
    note: Mapped[str] = mapped_column(
        String(256), default="", nullable=False, comment="用户填写的专注内容"
    )
    xp_earned: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="本次获得 XP"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False, comment="完成时间"
    )