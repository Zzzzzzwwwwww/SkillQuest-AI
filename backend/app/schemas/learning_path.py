"""
SkillQuest AI 个性化导学 Schema（模块5）。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# -------------------------------------------------------------------- #
# 生成 / 地图
# -------------------------------------------------------------------- #
class StageNodeOut(BaseModel):
    """路径中的单个节点（地图/详情复用）。"""

    id: int
    skill_node_id: int
    name: str = ""
    node_type: str = ""
    capability: str = ""
    stage: str
    order_no: int
    status: str = ""
    estimated_hours: int
    importance: int = 0
    required_level: int = 0
    mastery: int = 0
    gap: float = 0
    progress_percent: int = 0
    last_position: Optional[str] = None
    prerequisites: List[str] = []


class LearningPathMapOut(BaseModel):
    """学习路径地图（6 段位）。"""

    path_id: int
    target_job: str
    path_name: str
    status: str
    current_node_id: Optional[int] = None
    total_nodes: int
    mastered_nodes: int
    overall_progress: int
    stages: Dict[str, List[StageNodeOut]]
    stage_order: List[str]


class GeneratePathOut(BaseModel):
    """生成结果：路径地图 + 概要 meta。"""

    path: LearningPathMapOut
    meta: Dict[str, Any]
    agent_note: str = ""


# -------------------------------------------------------------------- #
# 进度更新 / 断点续学
# -------------------------------------------------------------------- #
class UpdateProgressIn(BaseModel):
    """更新节点学习进度。"""

    path_id: int
    skill_node_id: int
    progress_percent: int = Field(0, ge=0, le=100, description="进度 0-100")
    last_position: Optional[str] = Field(
        None, max_length=256, description="断点位置(章节/页码/时间)"
    )


class UpdateProgressOut(BaseModel):
    """更新结果：新的地图 + 当前节点指针。"""

    path: LearningPathMapOut
    updated_node: Optional[StageNodeOut] = None
    to_next: bool = False


class ResumePathOut(BaseModel):
    """断点续学：返回上次位置与当前节点。"""

    path: LearningPathMapOut
    resume_node: Optional[StageNodeOut] = None
    resume_position: Optional[str] = None
    hint: str = ""


class ResumeIn(BaseModel):
    """指定路径（可选，默认当前进行中路径）。"""

    path_id: Optional[int] = None


# -------------------------------------------------------------------- #
# 资源推荐
# -------------------------------------------------------------------- #
class ResourceOut(BaseModel):
    """学习资源（含规则推荐理由与评分）。"""

    resource_id: int
    title: str
    type: str
    type_label: str
    url: str
    skill_node_id: int
    difficulty: int
    duration: int
    description: str
    reason: str
    score: int


class RecommendIn(BaseModel):
    """资源推荐参数。"""

    skill_node_id: Optional[int] = None  # 缺省用当前路径节点
    resource_type: Optional[str] = Field(
        None, description="按资源类型过滤 video/course/article/exercise"
    )
    limit: int = Field(8, ge=1, le=20)


# -------------------------------------------------------------------- #
# regenerate 请求
# -------------------------------------------------------------------- #
class GeneratePathIn(BaseModel):
    """生成学习路径的入参（可选覆盖画像目标岗位）。"""

    job_id: Optional[int] = Field(None, description="指定岗位ID(缺省取画像target_job)")
    job_name: Optional[str] = Field(None, description="按岗位名称查找(二选一)")
    force: bool = Field(False, description="强制重新生成(覆盖进行中的路径)")