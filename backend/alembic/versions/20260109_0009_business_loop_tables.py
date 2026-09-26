"""add business loop tables

模块8：业务闭环 —— 新增 2 张表：
  1. weakness_diagnostics  弱点诊断（阶段测评后自动生成，AI 导师推送）
  2. boss_challenges       Boss 挑战记录（完成后自动发放 XP / 升级技能等级）

Revision ID: 20260109_0009
Revises: 20260108_0008
Create Date: 2026-01-09 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260109_0009"
down_revision: str = "20260108_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级：新建业务闭环 2 张表。"""
    op.create_table(
        "weakness_diagnostics",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("record_id", sa.BigInteger(), nullable=False, comment="来源测评记录ID"),
        sa.Column("knowledge_point_id", sa.BigInteger(), nullable=True, comment="知识点ID"),
        sa.Column("kp_name", sa.String(length=128), nullable=False, comment="知识点名称"),
        sa.Column("domain", sa.String(length=128), nullable=False, comment="能力域"),
        sa.Column("mastery_score", sa.Integer(), nullable=False, comment="当前掌握度"),
        sa.Column("diagnosis", sa.Text(), nullable=False, comment="规则诊断与建议"),
        sa.Column("status", sa.String(length=16), nullable=False, comment="状态"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["skill_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["record_id"], ["exam_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "record_id", "knowledge_point_id",
                            name="uq_weakness_user_record_kp"),
        sa.Index("ix_weakness_user_status", "user_id", "status"),
        comment="弱点诊断表",
    )
    op.create_table(
        "boss_challenges",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("skill_node_id", sa.BigInteger(), nullable=False, comment="挑战技能节点ID"),
        sa.Column("skill_name", sa.String(length=128), nullable=False, comment="挑战技能名称"),
        sa.Column("score", sa.Integer(), nullable=False, comment="挑战得分"),
        sa.Column("status", sa.String(length=16), nullable=False, comment="结果"),
        sa.Column("reward_xp", sa.Integer(), nullable=False, comment="发放XP"),
        sa.Column("result", sa.JSON(), nullable=True, comment="挑战明细"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.ForeignKeyConstraint(["skill_node_id"], ["skill_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_boss_user", "user_id", "created_at"),
        comment="Boss挑战记录表",
    )


def downgrade() -> None:
    """回滚：删除业务闭环 2 张表。"""
    op.drop_table("boss_challenges")
    op.drop_table("weakness_diagnostics")