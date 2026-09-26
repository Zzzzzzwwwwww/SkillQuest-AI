"""
SkillQuest AI ORM 基类模块

声明式基类 Base 供所有模型继承；
同时在此导出所有模型，供 Alembic autogenerate 自动发现。
"""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """全局 ORM 声明基类。

    注意：不要在基类声明 id/created_at/updated_at 的 Mapped 注解，
    否则子类未显式覆盖时会生成无默认值的裸列。
    这些字段由各模型或 TimestampMixin 显式定义。
    """

    # 表中常用字段的统一时间格式（MySQL DATETIME(6)）
    type_annotation_map = {
        datetime: DATETIME(fsp=6),
    }


class TimestampMixin:
    """为模型自动注入 created_at / updated_at 字段。"""

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=func.now(),
        server_onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )


# 导入模型，确保注册到 Base.metadata（Alembic autogenerate 依赖）
from app.models import (  # noqa: E402, F401
    user,
    profile,
    learning,
    assessment,
    persona,
    skill,
    learning_path,
    chat,
    assessment_review,
    business_loop,
    gamification,
)