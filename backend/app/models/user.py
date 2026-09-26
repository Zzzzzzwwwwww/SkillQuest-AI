"""
SkillQuest AI 用户模型

表结构 users：
  - id            主键
  - username      用户名（唯一索引）
  - email         邮箱（唯一索引）
  - password_hash 密码哈希（bcrypt，绝不保存明文）
  - phone         手机号（可空）
  - avatar        头像 URL（可空）
  - status        状态：1 正常 / 0 禁用
  - created_at    创建时间
  - updated_at    更新时间
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# 账号状态
USER_STATUS_NORMAL = 1
USER_STATUS_DISABLED = 0


class User(Base, TimestampMixin):
    """平台用户表，对应成长档案 / 角色 / 等级的核心主体。"""

    __tablename__ = "users"
    __table_args__ = {"comment": "平台用户表"}

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    username: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False, comment="用户名"
    )
    email: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False, comment="邮箱"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希(bcrypt)"
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, default=None, comment="手机号"
    )
    avatar: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True, default=None, comment="头像URL"
    )
    status: Mapped[int] = mapped_column(
        SmallInteger,
        default=USER_STATUS_NORMAL,
        nullable=False,
        comment="账号状态 1正常 0禁用",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username!r}, email={self.email!r})>"