"""
SkillQuest AI 测评模块 Schema（模块3：职业测评与画像）

注意：题目下发时只带展示字段（options/scale/placeholder），
评分规则 score_rule 仅在服务端使用，绝不下发前端（防作弊）。
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


# -------------------------------------------------------------------- #
# 题目 / 试卷（下发前端）
# -------------------------------------------------------------------- #
class QuestionOptionOut(BaseModel):
    """题目选项（展示文本）。"""

    key: str
    label: str


class ScaleSpecOut(BaseModel):
    """量表题型展示参数。"""

    min: int = 1
    max: int = 5
    step: int = 1
    labels: Optional[List[str]] = None


class QuestionOut(BaseModel):
    """题目出参（不含评分规则）。"""

    id: int
    paper_id: int
    question_type: str
    content: str
    dimension: str
    dimension_label: str
    order_no: int
    options: Optional[List[QuestionOptionOut]] = None
    scale: Optional[ScaleSpecOut] = None
    placeholder: Optional[str] = None


class PaperOut(BaseModel):
    """试卷出参（仅 active 试卷可作答）。"""

    id: int
    title: str
    description: Optional[str] = None
    type: str
    status: str
    question_count: int = 0
    created_at: str


# -------------------------------------------------------------------- #
# 提交 / 结果
# -------------------------------------------------------------------- #
class AnswerItemIn(BaseModel):
    """单题作答提交。"""

    question_id: int
    answer: Union[str, int, float, List[Any], None] = None


class AssessmentSubmitIn(BaseModel):
    """提交测评请求体。"""

    paper_id: int
    answers: List[AnswerItemIn] = Field(..., min_length=1)
    duration: Optional[int] = Field(0, ge=0, description="作答耗时(秒)")


class SkillGapOut(BaseModel):
    """岗位技能差距项。"""

    skill: str
    dimension: str
    current: float
    threshold: float
    gap: float


class RecommendedJobOut(BaseModel):
    """推荐岗位。"""

    job_id: str
    job_name: str
    summary: str
    match_score: float
    reason: str
    skill_gaps: List[SkillGapOut] = []


class RadarPointOut(BaseModel):
    """雷达图数据点。"""

    name: str
    key: str
    score: float


class AssessmentResultOut(BaseModel):
    """测评结果出参（总分 / 维度分 / 雷达图 / 职业推荐）。"""

    id: int
    paper_id: int
    paper_title: str
    total_score: float
    dimension_scores: Dict[str, float]
    dimension_labels: Dict[str, str]
    radar_data: Dict[str, List[RadarPointOut]]
    recommended_jobs: List[RecommendedJobOut]
    recommendation_source: str
    created_at: str


class AssessmentSubmitOut(BaseModel):
    """提交后立即返回的摘要。"""

    result_id: int
    total_score: float
    top_job: Optional[str] = None