"""
SkillQuest AI 用户画像模型

表结构 user_profiles：与 users 一对一，记录用户的个人信息与学习偏好。
  - id                主键
  - user_id           用户ID（唯一，外键）
  - real_name         真实姓名
  - education         学历
  - major             专业
  - school            学校
  - company           公司
  - job_intention     求职意向/目标岗位
  - learning_goal     学习目标
  - daily_study_time  每日计划学习时长（分钟）
  - created_at / updated_at
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class UserProfile(Base, TimestampMixin):
    """用户画像（一对一）。"""

    __tablename__ = "user_profiles"
    __table_args__ = {"comment": "用户画像表"}

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
        comment="用户ID",
    )
    real_name: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, default=None, comment="真实姓名"
    )
    education: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, default=None, comment="学历"
    )
    major: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, default=None, comment="专业"
    )
    school: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, default=None, comment="学校"
    )
    company: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, default=None, comment="公司"
    )
    job_intention: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, default=None, comment="求职意向岗位"
    )
    learning_goal: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None, comment="学习目标"
    )
    daily_study_time: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False, comment="每日计划学习时长(分钟)"
    )

    def __repr__(self) -> str:
        return f"<UserProfile(user_id={self.user_id})>"