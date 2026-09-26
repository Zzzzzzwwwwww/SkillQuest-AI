"""
SkillQuest AI 用户画像接口（模块3）

  - GET  /persona/current   当前画像（未生成时 data=null）
  - POST /persona/generate  基于最近一次测评生成/刷新画像

原则（第1条）：画像标签、雷达图、兴趣/价值观解析全部规则计算；
第3条：Career Agent 仅增强综述文本，LLM 不可用时自动降级为规则模板。
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.response import success
from app.core.security import get_current_user
from app.db.session import get_db
from app.models import (
    AssessmentAnswer,
    AssessmentQuestion,
    AssessmentResult,
    UserPersona,
)
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.persona import AbilityRadarOut, PersonaGenerateOut, PersonaOut
from app.services.assessment_scoring import (
    DIM_CAREER_INTENT,
    DIM_INTEREST,
    DIM_LEARNING_GOAL,
    DIM_WORK_VALUES,
    resolve_preference_answers,
)
from app.services.persona_builder import (
    build_persona_payload,
    enhance_persona_with_career_agent,
    summarize_text_answers,
)

router = APIRouter(prefix="/persona", tags=["persona"])


# -------------------------------------------------------------------- #
# 出参组装
# -------------------------------------------------------------------- #
def _to_persona_out(persona: UserPersona) -> PersonaOut:
    """把 user_personas 模型组装为前端可直接渲染的结构。"""
    tags_json: Dict[str, Any] = persona.persona_tags_json or {}
    radar: Dict[str, Any] = persona.ability_radar_json or {"dimensions": []}
    return PersonaOut(
        id=persona.id,
        user_id=persona.user_id,
        persona_tags=list(tags_json.get("tags") or []),
        persona_summary=str(tags_json.get("summary") or ""),
        strengths=list(tags_json.get("strengths") or []),
        weaknesses=list(tags_json.get("weaknesses") or []),
        advice=str(tags_json.get("advice") or ""),
        ai_enriched=bool(tags_json.get("ai_enriched")),
        ability_radar=AbilityRadarOut(dimensions=radar.get("dimensions") or []),
        interest=persona.interest_json or {},
        values=persona.values_json or {},
        learning_goal=persona.learning_goal,
        target_job=persona.target_job,
        created_at=persona.created_at.isoformat() if persona.created_at else "",
        updated_at=persona.updated_at.isoformat() if persona.updated_at else "",
    )


# -------------------------------------------------------------------- #
# 查询当前画像
# -------------------------------------------------------------------- #
@router.get(
    "/current",
    response_model=ApiResponse[Optional[PersonaOut]],
    summary="查询当前用户画像",
)
def get_current_persona(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """未生成画像时返回 data=null（前端据此引导用户完成测评）。"""
    persona = db.scalar(
        select(UserPersona).where(UserPersona.user_id == user.id)
    )
    if persona is None:
        return {"code": 0, "message": "success", "data": None}
    return success(_to_persona_out(persona))


# -------------------------------------------------------------------- #
# 生成 / 刷新画像
# -------------------------------------------------------------------- #
@router.post(
    "/generate",
    response_model=ApiResponse[PersonaGenerateOut],
    summary="生成/刷新用户画像",
    description="基于最近一次测评结果，规则构建画像并用 Career Agent(可选)增强综述。",
)
async def generate_persona(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """取最近测评结果 → 规则解析作答 → 构建画像载荷 → AI 增强(可选) → upsert。"""
    result = db.scalar(
        select(AssessmentResult)
        .where(AssessmentResult.user_id == user.id)
        .order_by(AssessmentResult.id.desc())
    )
    if result is None:
        raise HTTPException(status_code=400, detail="尚未完成任何测评，请先完成职业测评")

    # ---- 依据结果还原题目与原始答案，解析偏好（兴趣/价值观/文本答案）----
    questions = db.scalars(
        select(AssessmentQuestion)
        .where(AssessmentQuestion.paper_id == result.paper_id)
        .order_by(AssessmentQuestion.order_no.asc(), AssessmentQuestion.id.asc())
    ).all()
    answers = db.scalars(
        select(AssessmentAnswer).where(
            AssessmentAnswer.user_id == user.id,
            AssessmentAnswer.paper_id == result.paper_id,
        )
    ).all()
    ans_by_qid = {a.question_id: (a.answer_json or {}).get("value") for a in answers}
    raw_answers: List[Any] = [ans_by_qid.get(q.id) for q in questions]

    interest_data = resolve_preference_answers(
        questions, raw_answers, [DIM_INTEREST]
    )
    values_data = resolve_preference_answers(
        questions, raw_answers, [DIM_WORK_VALUES, DIM_LEARNING_GOAL, DIM_CAREER_INTENT]
    )
    text_answers = [
        str(raw) for raw in raw_answers if isinstance(raw, str) and raw.strip()
    ]
    learning_goal = _extract_text_answer(values_data, DIM_LEARNING_GOAL) or None
    job_intention = _extract_text_answer(values_data, DIM_CAREER_INTENT) or None

    # ---- 规则构建核心载荷 ----
    payload = build_persona_payload(
        dimension_scores=result.dimension_scores_json or {},
        interest_data=interest_data or None,
        values_data=values_data or None,
        recomm_result=result.recommended_jobs_json or {"source": "rule", "jobs": []},
        learning_goal=learning_goal,
        job_intention=job_intention,
    )
    # ---- Career Agent 增强（可选，未配置 LLM 时规则降级）----
    payload = await enhance_persona_with_career_agent(
        payload,
        dimension_scores=result.dimension_scores_json or {},
        recomm_result=result.recommended_jobs_json or {"source": "rule", "jobs": []},
        raw_answers_summary=summarize_text_answers(text_answers),
    )

    # ---- upsert 画像 ----
    persona = db.scalar(
        select(UserPersona).where(UserPersona.user_id == user.id)
    )
    if persona is None:
        persona = UserPersona(user_id=user.id)
        db.add(persona)
    persona.persona_tags_json = payload["persona_tags_json"]
    persona.ability_radar_json = payload["ability_radar_json"]
    persona.interest_json = payload["interest_json"]
    persona.values_json = payload["values_json"]
    persona.learning_goal = payload["learning_goal"]
    persona.target_job = payload["target_job"]
    db.commit()
    db.refresh(persona)

    return success(
        PersonaGenerateOut(
            persona=_to_persona_out(persona),
            source_result_id=result.id,
        )
    )


def _extract_text_answer(
    values_data: Dict[str, Any], dimension: str
) -> Optional[str]:
    """从解析后的偏好数据中取该维度第一条文本答案。"""
    items = values_data.get(dimension) or []
    for item in items:
        raw = item.get("raw")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None