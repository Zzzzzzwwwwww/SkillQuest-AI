"""
SkillQuest AI 自动画像生成（业务闭环2）

职业测评提交后自动触发画像生成并回写目标岗位。

原则（第1条）：画像标签/雷达/目标岗位全部规则计算；
Agent 综述增强仍由 POST /persona/generate 提供，本服务走同步规则路径（LLM 不阻塞提交）。
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AssessmentAnswer,
    AssessmentQuestion,
    AssessmentResult,
    UserPersona,
)
from app.services.assessment_scoring import (
    DIM_CAREER_INTENT,
    DIM_INTEREST,
    DIM_LEARNING_GOAL,
    DIM_WORK_VALUES,
    resolve_preference_answers,
)
from app.services.persona_builder import build_persona_payload


def _extract_text_answer(
    values_data: Dict[str, Any], dimension: str
) -> Optional[str]:
    """从解析后的偏好数据中提取某维度第一条文本答案。"""
    items = values_data.get(dimension) or []
    for item in items:
        raw = item.get("raw")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def build_persona_payload_from_result(
    db: Session, result: AssessmentResult
) -> Optional[Dict[str, Any]]:
    """依据测评结果规则构建画图像载荷（同步，无 Agent 增强）。"""
    questions = db.scalars(
        select(AssessmentQuestion)
        .where(AssessmentQuestion.paper_id == result.paper_id)
        .order_by(AssessmentQuestion.order_no.asc(), AssessmentQuestion.id.asc())
    ).all()
    answers = db.scalars(
        select(AssessmentAnswer).where(
            AssessmentAnswer.user_id == result.user_id,
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
    learning_goal = _extract_text_answer(values_data, DIM_LEARNING_GOAL) or None
    job_intention = _extract_text_answer(values_data, DIM_CAREER_INTENT) or None

    return build_persona_payload(
        dimension_scores=result.dimension_scores_json or {},
        interest_data=interest_data or None,
        values_data=values_data or None,
        recomm_result=result.recommended_jobs_json or {"source": "rule", "jobs": []},
        learning_goal=learning_goal,
        job_intention=job_intention,
    )


def auto_build_persona(db: Session, user_id: int) -> Optional[UserPersona]:
    """取用户最近一次测评结果自动生成/刷新画像（upsert）。

    Returns:
        画像对象；未曾测评时返回 None。
    """
    result = db.scalar(
        select(AssessmentResult)
        .where(AssessmentResult.user_id == user_id)
        .order_by(AssessmentResult.id.desc())
    )
    if result is None:
        return None

    payload = build_persona_payload_from_result(db, result)
    if payload is None:
        return None

    persona = db.scalar(
        select(UserPersona).where(UserPersona.user_id == user_id)
    )
    if persona is None:
        persona = UserPersona(user_id=user_id)
        db.add(persona)
    persona.persona_tags_json = payload["persona_tags_json"]
    persona.ability_radar_json = payload["ability_radar_json"]
    persona.interest_json = payload["interest_json"]
    persona.values_json = payload["values_json"]
    persona.learning_goal = payload["learning_goal"]
    persona.target_job = payload["target_job"]
    db.flush()
    return persona


def sync_target_job_to_archive(
    db: Session, user_id: int, target_job: Optional[str]
) -> None:
    """把目标岗位回写学习档案与个人资料（仅在未设置时写入）。"""
    if not target_job:
        return
    from app.models.learning import LearningArchive
    from app.models.profile import UserProfile

    archive = db.scalar(
        select(LearningArchive)
        .where(LearningArchive.user_id == user_id)
        .order_by(LearningArchive.id.desc())
    )
    if archive is not None and not archive.target_job:
        archive.target_job = target_job
        db.add(archive)

    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    if profile is not None and not profile.job_intention:
        profile.job_intention = target_job
        db.add(profile)