"""
SkillQuest AI 用户画像 Schema（模块3）。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AbilityRadarOut(BaseModel):
    """能力雷达图出参。"""

    dimensions: List[Dict[str, Any]]


class PersonaOut(BaseModel):
    """用户画像出参（persona_tags_json 内含 tags/summary/strengths/weaknesses/advice）。"""

    id: int
    user_id: int
    persona_tags: List[str] = []
    persona_summary: str = ""
    strengths: List[str] = []
    weaknesses: List[str] = []
    advice: str = ""
    ai_enriched: bool = False
    ability_radar: AbilityRadarOut
    interest: Dict[str, Any]
    values: Dict[str, Any]
    learning_goal: Optional[str] = None
    target_job: Optional[str] = None
    created_at: str
    updated_at: str


class PersonaGenerateOut(BaseModel):
    """画像生成出参（生成后与 PersonaOut 结构一致）。"""

    persona: PersonaOut
    source_result_id: Optional[int] = None