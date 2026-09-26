"""SkillQuest AI Boss 挑战 Schema（模块8 业务闭环6）。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BossStartIn(BaseModel):
    """Boss 挑战开始入参。"""

    skill_node_id: int = Field(..., description="挑战的技能节点ID(level2 技能)")


class BossQuestionOut(BaseModel):
    """Boss 挑战题目（不下发答案）。"""

    id: int
    question_type: str
    content: str
    options: List[Dict[str, str]] = Field(default_factory=list)
    score: int
    knowledge_point_id: Optional[int] = None


class BossStartOut(BaseModel):
    """Boss 挑战开始出参。"""

    challenge_id: int
    skill_node_id: int
    skill_name: str
    stage: str = ""
    description: str
    total_points: int
    questions: List[BossQuestionOut]
    source: str = "rule"


class BossAnswerItem(BaseModel):
    """Boss 挑战单题作答。"""

    question_id: int
    user_answer: Any = Field(..., description="答案(单选=key，多选=[keys]，判断=true/false)")


class BossFinishIn(BaseModel):
    """Boss 挑战完成入参。"""

    skill_node_id: int
    answers: List[BossAnswerItem] = Field(..., min_length=1)


class BossFinishOut(BaseModel):
    """Boss 挑战完成出参（含奖励与技能等级变化）。"""

    challenge_id: int
    skill_node_id: int
    skill_name: str
    score: int
    pass_flag: bool
    reward_xp: int
    archive_xp: int
    level: int
    xp_to_next_level: int
    skill_mastery: int
    skill_status: str
    message: str