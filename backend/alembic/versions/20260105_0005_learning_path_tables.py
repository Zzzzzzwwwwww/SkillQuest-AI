"""add learning path module tables

模块5：个性化导学 —— 新增 5 张表：
  1. learning_paths             学习路径（进行中/已完成）
  2. learning_path_nodes        路径节点（青铜~王者 6 段位）
  3. learning_resources         学习资源库
  4. learning_progress          节点学习进度（含断点位置）
  5. resource_recommendations   资源推荐记录

Revision ID: 20260105_0005
Revises: 20260104_0004
Create Date: 2026-01-05 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260105_0005"
down_revision: str = "20260104_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级：新建导学 5 张表。"""
    # ---------- learning_path_nodes（先建，供路径表 current_node_id 引用） ----------
    op.create_table(
        "learning_path_nodes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("path_id", sa.BigInteger(), nullable=False, comment="路径ID"),
        sa.Column("skill_node_id", sa.BigInteger(), nullable=False, comment="技能节点ID"),
        sa.Column("stage", sa.String(length=16), nullable=False, comment="段位 bronze/silver/gold/platinum/diamond/king"),
        sa.Column("order_no", sa.Integer(), nullable=False, comment="路径内序号(从1递增)"),
        sa.Column("status", sa.String(length=16), server_default="locked", nullable=False, comment="节点状态"),
        sa.Column("estimated_hours", sa.Integer(), server_default="6", nullable=False, comment="预计学习时长(小时)"),
        sa.Column("prerequisites_json", sa.JSON(), nullable=True, comment="前置技能名称数组"),
        sa.ForeignKeyConstraint(["skill_node_id"], ["skill_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path_id", "skill_node_id", name="uq_path_skill"),
        comment="学习路径节点表",
    )
    op.create_index("ix_path_nodes_path_order", "learning_path_nodes", ["path_id", "order_no"])

    # ---------- learning_paths ----------
    op.create_table(
        "learning_paths",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("target_job", sa.String(length=128), nullable=False, comment="目标岗位名称"),
        sa.Column("path_name", sa.String(length=128), nullable=False, comment="路径名称"),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False, comment="状态 active/completed"),
        sa.Column("current_node_id", sa.BigInteger(), nullable=True, comment="当前节点ID(断点续学指针)"),
        sa.Column("created_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"), nullable=False, comment="更新时间"),
        sa.ForeignKeyConstraint(["current_node_id"], ["learning_path_nodes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="学习路径表",
    )
    op.create_index("ix_learning_paths_user_status", "learning_paths", ["user_id", "status"])

    # ---------- learning_resources ----------
    op.create_table(
        "learning_resources",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("title", sa.String(length=256), nullable=False, comment="资源标题"),
        sa.Column("resource_type", sa.String(length=16), nullable=False, comment="类型 video/course/article/exercise"),
        sa.Column("url", sa.String(length=512), nullable=False, comment="资源链接"),
        sa.Column("skill_node_id", sa.BigInteger(), nullable=False, comment="关联技能节点ID"),
        sa.Column("difficulty", sa.Integer(), server_default="2", nullable=False, comment="难度 1-5"),
        sa.Column("duration", sa.Integer(), server_default="60", nullable=False, comment="预计时长(分钟)"),
        sa.Column("description", sa.Text(), nullable=True, comment="资源描述"),
        sa.ForeignKeyConstraint(["skill_node_id"], ["skill_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="学习资源表",
    )
    op.create_index("ix_learning_resources_skill", "learning_resources", ["skill_node_id"])

    # ---------- learning_progress ----------
    op.create_table(
        "learning_progress",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("path_id", sa.BigInteger(), nullable=False, comment="路径ID"),
        sa.Column("node_id", sa.BigInteger(), nullable=False, comment="路径节点ID"),
        sa.Column("progress_percent", sa.Integer(), server_default="0", nullable=False, comment="进度百分比 0-100"),
        sa.Column("last_position", sa.String(length=256), nullable=True, comment="断点位置(章节/页码/时间)"),
        sa.Column("updated_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"), nullable=False, comment="更新时间"),
        sa.ForeignKeyConstraint(["node_id"], ["learning_path_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["path_id"], ["learning_paths.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "path_id", "node_id", name="uq_user_path_node"),
        comment="学习进度表",
    )
    op.create_index("ix_learning_progress_user", "learning_progress", ["user_id"])

    # ---------- resource_recommendations ----------
    op.create_table(
        "resource_recommendations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("resource_id", sa.BigInteger(), nullable=False, comment="资源ID"),
        sa.Column("reason", sa.String(length=512), nullable=False, comment="推荐理由"),
        sa.Column("score", sa.Integer(), server_default="0", nullable=False, comment="推荐评分 0-100"),
        sa.Column("created_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False, comment="推荐时间"),
        sa.ForeignKeyConstraint(["resource_id"], ["learning_resources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="资源推荐记录表",
    )
    op.create_index("ix_resource_rec_user", "resource_recommendations", ["user_id"])


def downgrade() -> None:
    """回滚：删除 5 张表。"""
    op.drop_index("ix_resource_rec_user", table_name="resource_recommendations")
    op.drop_table("resource_recommendations")

    op.drop_index("ix_learning_progress_user", table_name="learning_progress")
    op.drop_table("learning_progress")

    op.drop_index("ix_learning_resources_skill", table_name="learning_resources")
    op.drop_table("learning_resources")

    op.drop_index("ix_learning_paths_user_status", table_name="learning_paths")
    op.drop_table("learning_paths")

    op.drop_index("ix_path_nodes_path_order", table_name="learning_path_nodes")
    op.drop_table("learning_path_nodes")