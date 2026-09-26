"""
SkillQuest AI 岗位技能图谱 Schema（模块4）。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# -------------------------------------------------------------------- #
# 岗位 / 技能树
# -------------------------------------------------------------------- #
class JobOut(BaseModel):
    """岗位出参。"""

    id: int
    job_name: str
    job_family: str
    description: Optional[str] = None
    industry: Optional[str] = None
    status: str
    skill_count: int = 0


class SkillNodeOut(BaseModel):
    """技能树节点（递归）。"""

    id: int
    name: str
    level: int
    node_type: str
    node_type_label: str
    description: str = ""
    importance: int
    required_level: Optional[int] = None
    status: str
    mastery_score: int
    prerequisites: List[str] = []
    children: List["SkillNodeOut"] = []


SkillNodeOut.model_rebuild()


class JobSkillTreeOut(BaseModel):
    """岗位分层技能树出参。"""

    job: JobOut
    tree: SkillNodeOut
    summary: Dict[str, Any]


# -------------------------------------------------------------------- #
# 用户技能状态
# -------------------------------------------------------------------- #
class UserSkillStatusItem(BaseModel):
    """单条用户技能状态。"""

    skill_node_id: int
    status: Optional[str] = None
    mastery_score: int = 0
    updated_at: Optional[str] = None


class UserSkillStatusOut(BaseModel):
    """当前技能掌握状态列表出参。"""

    total: int
    items: List[UserSkillStatusItem]


class UserSkillStatusSync(BaseModel):
    """批量同步技能状态请求。"""

    items: List[UserSkillStatusItem] = Field(..., min_length=1)


# -------------------------------------------------------------------- #
# 技能详情 / Gap
# -------------------------------------------------------------------- #
class PrerequisiteOut(BaseModel):
    """前置知识。"""

    id: Optional[int] = None
    name: str
    node_type: str
    mastery: int = 0
    status: str


class ResourceOut(BaseModel):
    """推荐资源（规则化）。"""

    type: str
    title: str
    desc: str


class RelatedJobOut(BaseModel):
    """关联岗位。"""

    job_id: int
    job_name: str
    job_family: str
    importance: int
    required_level: int


class SkillDetailOut(BaseModel):
    """技能详情出参。"""

    id: int
    name: str
    node_type: str
    node_type_label: str
    level: int
    description: str = ""
    importance: int
    mastery_score: int
    status: str
    prerequisites: List[PrerequisiteOut] = []
    resources: List[ResourceOut] = []
    related_jobs: List[RelatedJobOut] = []


class SkillGapItem(BaseModel):
    """Gap 分析单项。"""

    skill_id: int
    name: str
    importance: int
    required: int
    mastery: int
    gap: float


class SkillGapSummary(BaseModel):
    """Skill Gap 分析出参（行业/岗位要求 vs 我的能力）。"""

    overall_mastery: float
    fit_rate: float
    skill_count: int
    mastered_count: int
    gaps: List[SkillGapItem]


class JobSelectIn(BaseModel):
    """选定目标岗位入参。"""

    job_id: int = Field(..., description="岗位ID(jobs 表)")
    auto_generate_path: bool = Field(True, description="是否自动生成学习路径")


class JobSelectOut(BaseModel):
    """选定目标岗位出参。"""

    job_id: int
    job_name: str
    job_family: str
    target_job: str = ""
    auto_generated_path: bool = False
    path: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None