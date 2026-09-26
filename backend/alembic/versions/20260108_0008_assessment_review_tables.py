"""add assessment review module tables

模块7：学习评估复盘 —— 新增 6 张表：
  1. stage_exams            阶段测评试卷
  2. exam_questions         试卷题目（关联知识点）
  3. exam_records           测评记录（开始/提交）
  4. exam_answers           答题明细
  5. knowledge_mastery      知识点掌握度
  6. learning_reports       学习报告

Revision ID: 20260108_0008
Revises: 20260107_0007
Create Date: 2026-01-08 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260108_0008"
down_revision: str = "20260107_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级：新建评估复盘 6 张表。"""
    op.create_table(
        "stage_exams",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("title", sa.String(length=256), nullable=False, comment="试卷标题"),
        sa.Column("stage", sa.String(length=16), nullable=False, comment="阶段"),
        sa.Column("description", sa.Text(), nullable=False, comment="试卷说明"),
        sa.Column("total_score", sa.Integer(), nullable=False, comment="满分"),
        sa.Column("duration", sa.Integer(), nullable=False, comment="建议时长(分钟)"),
        sa.Column("status", sa.String(length=16), nullable=False, comment="状态"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_stage_exams_stage", "stage"),
        comment="阶段测评试卷表",
    )
    op.create_table(
        "exam_questions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("exam_id", sa.BigInteger(), nullable=False, comment="试卷ID"),
        sa.Column("question_type", sa.String(length=16), nullable=False, comment="题型"),
        sa.Column("content", sa.Text(), nullable=False, comment="题干"),
        sa.Column("options_json", sa.JSON(), nullable=True, comment="选项"),
        sa.Column("answer", sa.JSON(), nullable=False, comment="正确答案"),
        sa.Column("score", sa.Integer(), nullable=False, comment="分值"),
        sa.Column("knowledge_point_id", sa.BigInteger(), nullable=True, comment="关联知识点ID"),
        sa.ForeignKeyConstraint(["exam_id"], ["stage_exams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["skill_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_exam_questions_exam", "exam_id"),
        sa.Index("ix_exam_questions_kp", "knowledge_point_id"),
        comment="测评题目表",
    )
    op.create_table(
        "exam_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("exam_id", sa.BigInteger(), nullable=False, comment="试卷ID"),
        sa.Column("score", sa.Integer(), nullable=False, comment="得分(百分制)"),
        sa.Column("start_time", sa.DateTime(), nullable=False, comment="开始时间"),
        sa.Column("submit_time", sa.DateTime(), nullable=True, comment="提交时间"),
        sa.Column("status", sa.String(length=16), nullable=False, comment="状态"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.ForeignKeyConstraint(["exam_id"], ["stage_exams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_exam_records_user", "user_id", "created_at"),
        comment="测评记录表",
    )
    op.create_table(
        "exam_answers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("record_id", sa.BigInteger(), nullable=False, comment="测评记录ID"),
        sa.Column("question_id", sa.BigInteger(), nullable=False, comment="题目ID"),
        sa.Column("user_answer", sa.Text(), nullable=False, comment="用户答案"),
        sa.Column("is_correct", sa.Boolean(), nullable=False, comment="是否正确"),
        sa.Column("score", sa.Integer(), nullable=False, comment="本题得分"),
        sa.ForeignKeyConstraint(["question_id"], ["exam_questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["record_id"], ["exam_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_exam_answers_record", "record_id"),
        comment="答题明细表",
    )
    op.create_table(
        "knowledge_mastery",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("knowledge_point_id", sa.BigInteger(), nullable=False, comment="知识点ID"),
        sa.Column("mastery_score", sa.Integer(), nullable=False, comment="掌握度 0-100"),
        sa.Column("last_test_time", sa.DateTime(), nullable=False, comment="最近测评时间"),
        sa.Column("review_count", sa.Integer(), nullable=False, comment="复习/测评次数"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["skill_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "knowledge_point_id", name="uq_mastery_user_kp"),
        sa.Index("ix_mastery_user", "user_id"),
        comment="知识点掌握度表",
    )
    op.create_table(
        "learning_reports",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户ID"),
        sa.Column("report_type", sa.String(length=32), nullable=False, comment="报告类型"),
        sa.Column("report_json", sa.JSON(), nullable=False, comment="报告内容 JSON"),
        sa.Column("pdf_url", sa.String(length=512), nullable=True, comment="PDF链接"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_learning_reports_user", "user_id", "created_at"),
        comment="学习报告表",
    )


def downgrade() -> None:
    """回滚：删除 6 张表。"""
    op.drop_table("learning_reports")
    op.drop_table("knowledge_mastery")
    op.drop_table("exam_answers")
    op.drop_table("exam_records")
    op.drop_table("exam_questions")
    op.drop_table("stage_exams")