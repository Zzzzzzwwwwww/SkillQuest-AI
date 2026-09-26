"""add skill graph module tables

模块4：岗位技能图谱 —— 新增 4 张表：
  1. jobs                  岗位
  2. skill_nodes           技能节点树（自引用）
  3. job_skill_relations   岗位技能关系
  4. user_skill_status     用户技能掌握状态

Revision ID: 20260104_0004
Revises: 20260103_0003
Create Date: 2026-01-04 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260104_0004"
down_revision: str = "20260103_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级：新建技能图谱 4 张表。"""
    # ---------- jobs ----------
    op.create_table(
        "jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("job_name", sa.String(length=128), nullable=False, comment="岗位名称"),
        sa.Column("job_family", sa.String(length=64), nullable=False, comment="岗位族"),
        sa.Column("description", sa.Text(), nullable=True, comment="岗位描述"),
        sa.Column("industry", sa.String(length=64), nullable=True, comment="所属行业"),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False, comment="状态 active/offline"),
        sa.Column("created_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        comment="岗位表",
    )
    op.create_index("ix_jobs_family_status", "jobs", ["job_family", "status"])

    # ---------- skill_nodes ----------
    op.create_table(
        "skill_nodes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("name", sa.String(length=128), nullable=False, comment="节点名称"),
        sa.Column("parent_id", sa.BigInteger(), nullable=True, comment="父节点ID(自引用)"),
        sa.Column("level", sa.Integer(), server_default="1", nullable=False, comment="层级 1/2/3"),
        sa.Column("node_type", sa.String(length=16), nullable=False, comment="capability/skill/knowledge"),
        sa.Column("description", sa.Text(), nullable=True, comment="节点描述"),
        sa.Column("importance", sa.Integer(), server_default="50", nullable=False, comment="重要度(0-100)"),
        sa.Column("prerequisites_json", sa.JSON(), nullable=True, comment="前置知识名称数组"),
        sa.Column("created_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"), nullable=False, comment="更新时间"),
        sa.ForeignKeyConstraint(["parent_id"], ["skill_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="技能节点表",
    )
    op.create_index("ix_skill_nodes_parent", "skill_nodes", ["parent_id"])
    op.create_index("ix_skill_nodes_type_level", "skill_nodes", ["node_type", "level"])

    # ---------- job_skill_relations ----------
    op.create_table(
        "job_skill_relations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("job_id", sa.BigInteger(), nullable=False, comment="岗位ID"),
        sa.Column("skill_node_id", sa.BigInteger(), nullable=False, comment="技能节点ID"),
        sa.Column("importance", sa.Integer(), server_default="50", nullable=False, comment="对岗位的重要度(0-100)"),
        sa.Column("required_level", sa.Integer(), server_default="60", nullable=False, comment="岗位要求掌握度(0-100)"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_node_id"], ["skill_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "skill_node_id", name="uq_job_skill"),
        comment="岗位技能关系表",
    )
    op.create_index("ix_job_skill_relations_job_id", "job_skill_relations", ["job_id"])
    op.create_index("ix_relations_skill", "job_skill_relations", ["skill_node_id"])

    # ---------- user_skill_status ----------
    op.create_table(
        "user_skill_status",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("skill_node_id", sa.BigInteger(), nullable=False, comment="技能节点ID"),
        sa.Column("status", sa.String(length=16), server_default="not_started", nullable=False, comment="掌握状态 mastered/learning/not_started"),
        sa.Column("mastery_score", sa.Integer(), server_default="0", nullable=False, comment="掌握度(0-100)"),
        sa.Column("updated_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"), nullable=False, comment="更新时间"),
        sa.ForeignKeyConstraint(["skill_node_id"], ["skill_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "skill_node_id", name="uq_user_skill"),
        comment="用户技能状态表",
    )
    op.create_index("ix_user_skill_status_user", "user_skill_status", ["user_id"])


def downgrade() -> None:
    """回滚：删除 4 张表。"""
    op.drop_index("ix_user_skill_status_user", table_name="user_skill_status")
    op.drop_table("user_skill_status")

    op.drop_index("ix_relations_skill", table_name="job_skill_relations")
    op.drop_index("ix_job_skill_relations_job_id", table_name="job_skill_relations")
    op.drop_table("job_skill_relations")

    op.drop_index("ix_skill_nodes_type_level", table_name="skill_nodes")
    op.drop_index("ix_skill_nodes_parent", table_name="skill_nodes")
    op.drop_table("skill_nodes")

    op.drop_index("ix_jobs_family_status", table_name="jobs")
    op.drop_table("jobs")