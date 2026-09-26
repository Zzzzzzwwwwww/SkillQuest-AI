"""add assessment & persona tables

模块3：职业测评与画像 —— 新增 5 张表：
  1. assessment_papers     测评试卷
  2. assessment_questions  测评题目
  3. assessment_answers    用户作答流水
  4. assessment_results    测评结果
  5. user_personas         用户画像

Revision ID: 20260103_0003
Revises: 20260102_0002
Create Date: 2026-01-03 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260103_0003"
down_revision: str = "20260102_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级：新建测评与画像 5 张表。"""
    # ---------- assessment_papers ----------
    op.create_table(
        "assessment_papers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("title", sa.String(length=128), nullable=False, comment="试卷标题"),
        sa.Column("description", sa.Text(), nullable=True, comment="试卷说明"),
        sa.Column("type", sa.String(length=32), nullable=False, comment="试卷类型 career/stage/boss"),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False, comment="状态 draft/active/offline"),
        sa.Column("created_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        comment="测评试卷表",
    )

    # ---------- assessment_questions ----------
    op.create_table(
        "assessment_questions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("paper_id", sa.BigInteger(), nullable=False, comment="所属试卷ID"),
        sa.Column("question_type", sa.String(length=16), nullable=False, comment="题型 single/multiple/scale/text"),
        sa.Column("content", sa.Text(), nullable=False, comment="题目内容"),
        sa.Column("options_json", sa.JSON(), nullable=True, comment="选项展示文本 {A: 文本}"),
        sa.Column("dimension", sa.String(length=32), nullable=False, comment="测评维度"),
        sa.Column("score_rule", sa.JSON(), nullable=False, comment="评分规则(服务端用)"),
        sa.Column("order_no", sa.Integer(), server_default="0", nullable=False, comment="题序"),
        sa.ForeignKeyConstraint(["paper_id"], ["assessment_papers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="测评题目表",
    )
    op.create_index("ix_questions_paper_order", "assessment_questions", ["paper_id", "order_no"])

    # ---------- assessment_answers ----------
    op.create_table(
        "assessment_answers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("paper_id", sa.BigInteger(), nullable=False, comment="试卷ID"),
        sa.Column("question_id", sa.BigInteger(), nullable=False, comment="题目ID"),
        sa.Column("answer_json", sa.JSON(), nullable=False, comment="原始答案 {value: ...}"),
        sa.Column("score", sa.Float(), server_default="0", nullable=False, comment="服务端得分(0-100)"),
        sa.Column("created_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False, comment="作答时间"),
        sa.ForeignKeyConstraint(["paper_id"], ["assessment_papers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["assessment_questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="测评作答表",
    )
    op.create_index("ix_assessment_answers_user_id", "assessment_answers", ["user_id"])
    op.create_index("ix_answers_user_paper", "assessment_answers", ["user_id", "paper_id"])

    # ---------- assessment_results ----------
    op.create_table(
        "assessment_results",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("paper_id", sa.BigInteger(), nullable=False, comment="试卷ID"),
        sa.Column("total_score", sa.Float(), server_default="0", nullable=False, comment="总分(0-100)"),
        sa.Column("dimension_scores_json", sa.JSON(), nullable=False, comment="维度得分 {dim: 0-100}"),
        sa.Column("recommended_jobs_json", sa.JSON(), nullable=False, comment="职业推荐(JSON)"),
        sa.Column("created_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False, comment="测评时间"),
        sa.ForeignKeyConstraint(["paper_id"], ["assessment_papers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="测评结果表",
    )
    op.create_index("ix_assessment_results_user_id", "assessment_results", ["user_id"])
    op.create_index("ix_results_user_created", "assessment_results", ["user_id", "created_at"])

    # ---------- user_personas ----------
    op.create_table(
        "user_personas",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("persona_tags_json", sa.JSON(), nullable=False, comment="画像标签/综述/优势/短板(JSON)"),
        sa.Column("ability_radar_json", sa.JSON(), nullable=False, comment="能力雷达图数据(JSON)"),
        sa.Column("interest_json", sa.JSON(), nullable=True, comment="兴趣数据(JSON)"),
        sa.Column("values_json", sa.JSON(), nullable=True, comment="职业价值观数据(JSON)"),
        sa.Column("learning_goal", sa.Text(), nullable=True, comment="学习目标"),
        sa.Column("target_job", sa.String(length=128), nullable=True, comment="目标职业"),
        sa.Column("created_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(fsp=6), server_default=sa.text("CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)"), nullable=False, comment="更新时间"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="用户画像表",
    )
    op.create_index("ix_user_personas_user_id", "user_personas", ["user_id"], unique=True)


def downgrade() -> None:
    """回滚：删除 5 张表。"""
    op.drop_index("ix_user_personas_user_id", table_name="user_personas")
    op.drop_table("user_personas")

    op.drop_index("ix_results_user_created", table_name="assessment_results")
    op.drop_index("ix_assessment_results_user_id", table_name="assessment_results")
    op.drop_table("assessment_results")

    op.drop_index("ix_answers_user_paper", table_name="assessment_answers")
    op.drop_index("ix_assessment_answers_user_id", table_name="assessment_answers")
    op.drop_table("assessment_answers")

    op.drop_index("ix_questions_paper_order", table_name="assessment_questions")
    op.drop_table("assessment_questions")

    op.drop_table("assessment_papers")