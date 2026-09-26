"""
SkillQuest AI 学习评估复盘模型（模块7）

表结构：
  - stage_exams          阶段测评试卷（青铜→王者 分阶段）
  - exam_questions       试卷题目（单选/多选/判断，含知识点关联 knowledge_point_id）
  - exam_records         用户测评记录（开始/提交、总分）
  - exam_answers         答题明细（用户答案、对错、得分）
  - knowledge_mastery    知识点掌握度（upsert 累计，热力图/报告数据源）
  - learning_reports     学习报告（Assessment Agent 增强 + 规则降级，可导 PDF）
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# 试卷状态
EXAM_ACTIVE = "active"
EXAM_DISABLED = "disabled"

# 题目类型
QT_SINGLE = "single"      # 单选
QT_MULTIPLE = "multiple"  # 多选
QT_JUDGE = "judge"        # 判断

# 测评记录状态
RECORD_PENDING = "pending"      # 已开始未提交
RECORD_SUBMITTED = "submitted"  # 已提交完成

# 报告类型
REPORT_EXAM = "exam_review"   # 测评复盘
REPORT_GENERAL = "general"    # 综合报告


class StageExam(Base):
    """阶段测评试卷（青铜→王者分段考核）。"""

    __tablename__ = "stage_exams"
    __table_args__ = (
        Index("ix_stage_exams_stage", "stage"),
        {"comment": "阶段测评试卷表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    title: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="试卷标题"
    )
    stage: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="阶段 bronze/silver/gold/platinum/diamond/king",
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="试卷说明"
    )
    total_score: Mapped[int] = mapped_column(
        Integer, default=100, nullable=False, comment="满分(总分)"
    )
    duration: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False, comment="建议时长(分钟)"
    )
    status: Mapped[str] = mapped_column(
        String(16), default=EXAM_ACTIVE, nullable=False, comment="状态 active/disabled"
    )


class ExamQuestion(Base):
    """试卷题目（含正确答案与知识点关联）。"""

    __tablename__ = "exam_questions"
    __table_args__ = (
        Index("ix_exam_questions_exam", "exam_id"),
        Index("ix_exam_questions_kp", "knowledge_point_id"),
        {"comment": "测评题目表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    exam_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("stage_exams.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属试卷ID",
    )
    question_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="题型 single/multiple/judge"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="题干"
    )
    options_json: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, default=list, comment="选项 [{key,label}]"
    )
    answer: Mapped[Any] = mapped_column(
        JSON, nullable=False, comment="正确答案(单选=key,多选=[keys],判断=true/false)"
    )
    score: Mapped[int] = mapped_column(
        Integer, default=10, nullable=False, comment="分值"
    )
    knowledge_point_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("skill_nodes.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        comment="关联知识点ID(skill_nodes.node_type=knowledge)",
    )


class ExamRecord(Base):
    """一次测评记录（开始→提交）。"""

    __tablename__ = "exam_records"
    __table_args__ = (
        Index("ix_exam_records_user", "user_id", "created_at"),
        {"comment": "测评记录表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户ID",
    )
    exam_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("stage_exams.id", ondelete="CASCADE"),
        nullable=False,
        comment="试卷ID",
    )
    score: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="得分(百分制 0-100)"
    )
    start_time: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False, comment="开始时间"
    )
    submit_time: Mapped[Optional[datetime]] = mapped_column(
        nullable=True, default=None, comment="提交时间"
    )
    status: Mapped[str] = mapped_column(
        String(16), default=RECORD_PENDING, nullable=False, comment="状态 pending/submitted"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False, comment="创建时间"
    )


class ExamAnswer(Base):
    """答题明细。"""

    __tablename__ = "exam_answers"
    __table_args__ = (
        Index("ix_exam_answers_record", "record_id"),
        {"comment": "答题明细表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    record_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("exam_records.id", ondelete="CASCADE"),
        nullable=False,
        comment="测评记录ID",
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("exam_questions.id", ondelete="CASCADE"),
        nullable=False,
        comment="题目ID",
    )
    user_answer: Mapped[str] = mapped_column(
        Text, nullable=False, comment="用户答案(JSON 序列化)"
    )
    is_correct: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否正确"
    )
    score: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="本题得分"
    )


class KnowledgeMastery(Base):
    """知识点掌握度（按次测评累计更新）。"""

    __tablename__ = "knowledge_mastery"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "knowledge_point_id", name="uq_mastery_user_kp"
        ),
        Index("ix_mastery_user", "user_id"),
        {"comment": "知识点掌握度表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户ID",
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skill_nodes.id", ondelete="CASCADE"),
        nullable=False,
        comment="知识点ID",
    )
    mastery_score: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="掌握度 0-100"
    )
    last_test_time: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False, comment="最近测评时间"
    )
    review_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="复习/测评次数"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False, comment="创建时间"
    )


class LearningReport(Base):
    """学习报告（测评复盘/综合报告，JSON 持久化，可导 PDF）。"""

    __tablename__ = "learning_reports"
    __table_args__ = (
        Index("ix_learning_reports_user", "user_id", "created_at"),
        {"comment": "学习报告表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户ID",
    )
    report_type: Mapped[str] = mapped_column(
        String(32), default=REPORT_EXAM, nullable=False, comment="报告类型"
    )
    report_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="报告内容 JSON"
    )
    pdf_url: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True, default=None, comment="导出的 PDF 链接"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False, comment="创建时间"
    )