"""rename learning_resources.resource_type to type

模块5-调整：将 learning_resources 表中的字段 resource_type 重命名为 type，
与前端资源类型字段保持一致（schema ResourceOut/接口输出已用 type）。

Revision ID: 20260107_0007
Revises: 20260106_0006
Create Date: 2026-01-07 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260107_0007"
down_revision: str = "20260106_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级：learning_resources.resource_type → type（保留注释）。"""
    op.alter_column(
        "learning_resources",
        "resource_type",
        new_column_name="type",
        existing_type=sa.String(length=16),
        existing_nullable=False,
        comment="类型 video/course/article/exercise",
    )


def downgrade() -> None:
    """回滚：type → resource_type。"""
    op.alter_column(
        "learning_resources",
        "type",
        new_column_name="resource_type",
        existing_type=sa.String(length=16),
        existing_nullable=False,
        comment="类型 video/course/article/exercise",
    )