"""add user module tables

模块2：用户管理 ——
  1. users 表扩展 phone / avatar / status 字段
  2. 新增 user_profiles / learning_archives / learning_records / assessment_reports

Revision ID: 20260102_0002
Revises: 20260101_0001
Create Date: 2026-01-02 00:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260102_0002"
down_revision: str = "20260101_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级：users 加列 + 新建 4 张表。"""
    # ---------- users 扩展 ----------
    op.add_column("users", sa.Column("phone", sa.String(length=20), nullable=True, comment="手机号"))
    op.add_column("users", sa.Column("avatar", sa.String(length=512), nullable=True, comment="头像URL"))
    op.add_column(
        "users",
        sa.Column("status", sa.SmallInteger(), server_default="1", nullable=False, comment="账号状态 1正常 0禁用"),
    )

    # ---------- user_profiles ----------
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("real_name", sa.String(length=64), nullable=True, comment="真实姓名"),
        sa.Column("education", sa.String(length=32), nullable=True, comment="学历"),
        sa.Column("major", sa.String(length=64), nullable=True, comment="专业"),
        sa.Column("school", sa.String(length=128), nullable=True, comment="学校"),
        sa.Column("company", sa.String(length=128), nullable=True, comment="公司"),
        sa.Column("job_intention", sa.String(length=128), nullable=True, comment="求职意向岗位"),
        sa.Column("learning_goal", sa.Text(), nullable=True, comment="学习目标"),
        sa.Column("daily_study_time", sa.Integer(), server_default="30", nullable=False, comment="每日计划学习时长(分钟)"),
        sa.Column("created_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"), nullable=False, comment="更新时间"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="用户画像表",
    )
    op.create_index("ix_user_profiles_user_id", "user_profiles", ["user_id"], unique=True)

    # ---------- learning_archives ----------
    op.create_table(
        "learning_archives",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("archive_name", sa.String(length=64), server_default="我的成长档案", nullable=False, comment="档案名称"),
        sa.Column("target_job", sa.String(length=128), nullable=True, comment="目标岗位"),
        sa.Column("current_level", sa.Integer(), server_default="1", nullable=False, comment="当前等级"),
        sa.Column("total_xp", sa.Integer(), server_default="0", nullable=False, comment="累计XP"),
        sa.Column("created_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"), nullable=False, comment="更新时间"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="学习档案表",
    )
    op.create_index("ix_learning_archives_user_id", "learning_archives", ["user_id"])

    # ---------- learning_records ----------
    op.create_table(
        "learning_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("module_type", sa.String(length=32), nullable=False, comment="模块类型"),
        sa.Column("action_type", sa.String(length=32), nullable=False, comment="动作类型"),
        sa.Column("target_id", sa.BigInteger(), nullable=True, comment="目标对象ID"),
        sa.Column("duration", sa.Integer(), server_default="0", nullable=False, comment="时长(秒)"),
        sa.Column("result", mysql.JSON().with_variant(sa.JSON(), "mysql"), nullable=True, comment="结果快照"),
        sa.Column("created_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False, comment="发生时间"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="学习轨迹表",
    )
    op.create_index("ix_learning_records_user_id", "learning_records", ["user_id"])
    op.create_index("ix_records_user_module", "learning_records", ["user_id", "module_type"])
    op.create_index("ix_records_user_created", "learning_records", ["user_id", "created_at"])

    # ---------- assessment_reports ----------
    op.create_table(
        "assessment_reports",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("assessment_id", sa.BigInteger(), nullable=True, comment="关联测评/考试/挑战ID"),
        sa.Column("report_type", sa.String(length=32), nullable=False, comment="报告类型"),
        sa.Column("report_json", mysql.JSON().with_variant(sa.JSON(), "mysql"), nullable=False, comment="报告内容(JSON)"),
        sa.Column("created_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"), nullable=False, comment="更新时间"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="测评报告表",
    )
    op.create_index("ix_assessment_reports_user_id", "assessment_reports", ["user_id"])
    op.create_index("ix_reports_user_type", "assessment_reports", ["user_id", "report_type"])


def downgrade() -> None:
    """回滚：删表并移除扩展列。"""
    op.drop_index("ix_reports_user_type", table_name="assessment_reports")
    op.drop_index("ix_assessment_reports_user_id", table_name="assessment_reports")
    op.drop_table("assessment_reports")

    op.drop_index("ix_records_user_created", table_name="learning_records")
    op.drop_index("ix_records_user_module", table_name="learning_records")
    op.drop_index("ix_learning_records_user_id", table_name="learning_records")
    op.drop_table("learning_records")

    op.drop_index("ix_learning_archives_user_id", table_name="learning_archives")
    op.drop_table("learning_archives")

    op.drop_index("ix_user_profiles_user_id", table_name="user_profiles")
    op.drop_table("user_profiles")

    op.drop_column("users", "status")
    op.drop_column("users", "avatar")
    op.drop_column("users", "phone")