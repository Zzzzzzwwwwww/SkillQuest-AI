"""create users table

初始迁移：创建 users 表。

Revision ID: 20260101_0001
Revises:
Create Date: 2026-01-01 00:00:00
"""

from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260101_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 users 表。"""
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("username", sa.String(length=64), nullable=False, comment="用户名"),
        sa.Column("email", sa.String(length=128), nullable=False, comment="邮箱"),
        sa.Column("password_hash", sa.String(length=255), nullable=False, comment="密码哈希"),
        sa.Column(
            "created_at",
            sa.DateTime(fsp=6),
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(fsp=6),
            server_default=sa.text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"),
            nullable=False,
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="平台用户表",
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    """回滚：删除 users 表。"""
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")