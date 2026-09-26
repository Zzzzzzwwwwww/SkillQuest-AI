"""
SkillQuest AI 测评相关模型（模块3 + 模块2报告表）

表结构：
  - assessment_reports  测评报告（模块2）：Agent 结构化输出落库
  - assessment_papers   测评试卷：职业测评卷 / 阶段考试卷 / Boss 评审卷
  - assessment_questions 测评题目：支持单选/多选/量表/简答
  - assessment_answers   用户作答流水：每题一次提交
  - assessment_results   测评结果：总分、维度分、推荐岗位（模块3）
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# 报告类型
REPORT_CAREER = "career"     # 职业测评画像
REPORT_STAGE = "stage"       # 阶段测评复盘
REPORT_BOSS = "boss"         # Boss 评审
REPORT_PERIODIC = "periodic" # 周期性学习报告

# 测评题型（模块3）
QUESTION_SINGLE = "single"    # 单选
QUESTION_MULTIPLE = "multiple"  # 多选
QUESTION_SCALE = "scale"      # 量表
QUESTION_TEXT = "text"        # 简答

# 试卷状态
PAPER_DRAFT = "draft"         # 草稿（不可作答）
PAPER_ACTIVE = "active"       # 已发布
PAPER_OFFLINE = "offline"     # 已下线


class AssessmentReport(Base, TimestampMixin):
    """测评报告：Agent 结构化输出落库，支持历史报告查询。"""

    __tablename__ = "assessment_reports"
    __table_args__ = (
        Index("ix_reports_user_type", "user_id", "report_type"),
        {"comment": "测评报告表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="用户ID",
    )
    assessment_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, default=None, comment="关联测评/考试/挑战ID"
    )
    report_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="报告类型 career/stage/boss/periodic"
    )
    report_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="报告内容(结构化JSON)"
    )


class AssessmentPaper(Base, TimestampMixin):
    """测评试卷：一套题目的容器。"""

    __tablename__ = "assessment_papers"
    __table_args__ = {"comment": "测评试卷表"}

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    title: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="试卷标题"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None, comment="试卷说明"
    )
    type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="试卷类型 career/stage/boss"
    )
    status: Mapped[str] = mapped_column(
        String(16), default=PAPER_ACTIVE, nullable=False, comment="状态 draft/active/offline"
    )


class AssessmentQuestion(Base):
    """测评题目：题型、选项、维度、评分规则。"""

    __tablename__ = "assessment_questions"
    __table_args__ = (
        Index("ix_questions_paper_order", "paper_id", "order_no"),
        {"comment": "测评题目表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    paper_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("assessment_papers.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属试卷ID",
    )
    question_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="题型 single/multiple/scale/text"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="题目内容"
    )
    options_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, default=None, comment="选项(展示文本) {A: 文本}"
    )
    dimension: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="测评维度"
    )
    score_rule: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="评分规则(服务端评分用, 不下发前端)"
    )
    order_no: Mapped[int] = mapped_column(
        default=0, nullable=False, comment="题序"
    )


class AssessmentAnswer(Base):
    """用户作答流水：每次提交的原始答案与服务端评分。"""

    __tablename__ = "assessment_answers"
    __table_args__ = (
        Index("ix_answers_user_paper", "user_id", "paper_id"),
        {"comment": "测评作答表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="用户ID",
    )
    paper_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("assessment_papers.id", ondelete="CASCADE"),
        nullable=False,
        comment="试卷ID",
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("assessment_questions.id", ondelete="CASCADE"),
        nullable=False,
        comment="题目ID",
    )
    answer_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="原始答案 {value: ...}"
    )
    score: Mapped[float] = mapped_column(
        default=0.0, nullable=False, comment="服务端评出的得分(0-100)"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False, comment="作答时间"
    )


class AssessmentResult(Base):
    """测评结果：总分、维度得分、职业推荐，前端直接渲染。"""

    __tablename__ = "assessment_results"
    __table_args__ = (
        Index("ix_results_user_created", "user_id", "created_at"),
        {"comment": "测评结果表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="用户ID",
    )
    paper_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("assessment_papers.id", ondelete="CASCADE"),
        nullable=False,
        comment="试卷ID",
    )
    total_score: Mapped[float] = mapped_column(
        default=0.0, nullable=False, comment="总分(0-100)"
    )
    dimension_scores_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="维度得分 {dimension: 0-100}"
    )
    recommended_jobs_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="职业推荐 {source, jobs: [...]}"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False, comment="测评时间"
    )