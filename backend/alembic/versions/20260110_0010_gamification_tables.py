"""add gamification tables

模块9：游戏化系统 —— 新增 4 张表：
  1. achievements            成就定义（种子数据）
  2. user_achievements       用户已解锁成就
  3. xp_logs                 XP 流水
  4. pomodoro_sessions       番茄钟专注记录

Revision ID: 20260110_0010
Revises: 20260109_0009
Create Date: 2026-01-10 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260110_0010"
down_revision: str = "20260109_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级：新建游戏化 4 张表。"""
    op.create_table(
        "achievements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("name", sa.String(length=64), nullable=False, comment="成就唯一标识"),
        sa.Column("title", sa.String(length=64), nullable=False, comment="成就名称"),
        sa.Column("description", sa.String(length=256), nullable=False, comment="成就描述"),
        sa.Column("icon", sa.String(length=64), nullable=False, comment="图标标识"),
        sa.Column("condition_json", sa.JSON(), nullable=True, comment="解锁条件"),
        sa.Column("xp_reward", sa.Integer(), nullable=False, comment="解锁奖励XP"),
        sa.Column("hidden", sa.Integer(), nullable=False, comment="是否隐藏"),
        sa.Column("sort_order", sa.Integer(), nullable=False, comment="排序"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.Index("ix_achievements_name", "name"),
        comment="成就定义表",
    )
    op.create_table(
        "user_achievements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("achievement_id", sa.BigInteger(), nullable=False, comment="成就ID"),
        sa.Column("unlocked_at", sa.DateTime(), nullable=False, comment="解锁时间"),
        sa.ForeignKeyConstraint(["achievement_id"], ["achievements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
        sa.Index("ix_user_achievement_user", "user_id"),
        comment="用户成就表",
    )
    op.create_table(
        "xp_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("action_type", sa.String(length=32), nullable=False, comment="动作类型"),
        sa.Column("xp_amount", sa.Integer(), nullable=False, comment="本次获得XP"),
        sa.Column("note", sa.String(length=256), nullable=False, comment="说明"),
        sa.Column("metadata_json", sa.JSON(), nullable=True, comment="扩展信息"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="获得时间"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_xp_logs_user_action", "user_id", "action_type"),
        sa.Index("ix_xp_logs_user_created", "user_id", "created_at"),
        comment="XP流水表",
    )
    op.create_table(
        "pomodoro_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("mode", sa.String(length=16), nullable=False, comment="模式"),
        sa.Column("focus_minutes", sa.Integer(), nullable=False, comment="专注分钟数"),
        sa.Column("break_minutes", sa.Integer(), nullable=False, comment="休息分钟数"),
        sa.Column("rounds", sa.Integer(), nullable=False, comment="完成轮数"),
        sa.Column("note", sa.String(length=256), nullable=False, comment="专注内容"),
        sa.Column("xp_earned", sa.Integer(), nullable=False, comment="获得XP"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="完成时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_pomodoro_user_created", "user_id", "created_at"),
        comment="番茄钟记录表",
    )


def downgrade() -> None:
    """回滚：删除游戏化 4 张表。"""
    op.drop_table("pomodoro_sessions")
    op.drop_table("xp_logs")
    op.drop_table("user_achievements")
    op.drop_table("achievements")