"""
SkillQuest AI 学习评估复盘 Schema（模块7）。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# -------------------------------------------------------------------- #
# 开始 / 提交
# -------------------------------------------------------------------- #
class ExamStartIn(BaseModel):
    """开始一次测评。"""

    exam_id: int


class ExamQuestionOut(BaseModel):
    """下发题目（不下发正确答案）。"""

    id: int
    question_type: str
    content: str
    options: List[Dict[str, str]] = Field(default_factory=list)
    score: int
    knowledge_point_id: Optional[int] = None


class ExamStartOut(BaseModel):
    """开始测评返回：记录 + 试卷信息 + 题目。"""

    record_id: int
    exam_id: int
    title: str
    stage: str
    description: str
    duration: int
    total_score: int
    end_time: str
    questions: List[ExamQuestionOut]


class AnswerItemIn(BaseModel):
    """单题作答。"""

    question_id: int
    user_answer: Any = Field(..., description="答案(单选=key，多选=[keys]，判断=true/false)")


class ExamSubmitIn(BaseModel):
    """提交测评答卷。"""

    record_id: int
    answers: List[AnswerItemIn] = Field(..., min_length=1)


class ExamSubmitOut(BaseModel):
    """提交结果摘要。"""

    record_id: int
    score: int
    correct_count: int
    total_count: int
    pass_flag: bool


# -------------------------------------------------------------------- #
# 结果详情
# -------------------------------------------------------------------- #
class QuestionResultItem(BaseModel):
    """单题结果。"""

    question_id: int
    content: str
    is_correct: bool
    points_earned: int
    points_total: int
    correct_answer: Any
    user_answer: Any


class MasteryItemOut(BaseModel):
    """知识点掌握度条目。"""

    knowledge_point_id: Optional[int] = None
    name: str
    domain: str = ""
    mastery_score: int
    last_test_time: Optional[str] = None
    review_count: int = 0


class RadarPointOut(BaseModel):
    """能力雷达点（按能力域聚合掌握度）。"""

    domain: str
    value: int


class TrendPointOut(BaseModel):
    """学习趋势点（历次测评）。"""

    record_id: int
    exam_title: str
    score: int
    submitted_at: str


class WeakPointOut(BaseModel):
    """薄弱知识点 / 下一步。"""

    knowledge_point_id: Optional[int] = None
    name: str
    mastery_score: int
    suggestion: str = ""


class ExamResultOut(BaseModel):
    """测评结果详情。"""

    record_id: int
    exam_id: int
    exam_title: str
    stage: str
    score: int
    correct_count: int
    total_count: int
    submitted_at: str
    questions: List[QuestionResultItem]
    mastery: List[MasteryItemOut]
    radar: List[RadarPointOut]
    trend: List[TrendPointOut]
    weak_points: List[WeakPointOut]
    next_steps: List[str]


# -------------------------------------------------------------------- #
# 掌握度
# -------------------------------------------------------------------- #
class MasteryOut(BaseModel):
    """掌握度总览（含热力图数据）。"""

    items: List[MasteryItemOut]
    heatmap: Dict[str, Any] = Field(default_factory=dict)


# -------------------------------------------------------------------- #
# 学习报告
# -------------------------------------------------------------------- #
class ReportGenerateIn(BaseModel):
    """生成学习报告。"""

    record_id: Optional[int] = Field(None, description="指定测评记录(缺省用最近一次)")
    report_type: str = Field("exam_review", description="报告类型 exam_review/general")


class ReportOut(BaseModel):
    """学习报告详情。"""

    id: int
    report_type: str
    report_json: Dict[str, Any]
    ai_enriched: bool = False
    pdf_url: Optional[str] = None
    created_at: str