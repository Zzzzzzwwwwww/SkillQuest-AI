"""
SkillQuest AI 职业测评接口（模块3）

  - GET  /assessment/papers     可用试卷列表（active）
  - GET  /assessment/questions  获取试卷题目（不下发评分规则）
  - POST /assessment/submit     提交答卷：服务端规则评分 → 阈值推荐 → 落库
  - GET  /assessment/result/{id} 测评结果详情（雷达图/推荐岗位/技能差距）

原则（第1条）：每题得分、维度得分、总分、职位匹配全部规则计算，AI 不参与算分。
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.response import success
from app.core.security import get_current_user
from app.db.session import get_db
from app.models import (
    AssessmentAnswer,
    AssessmentPaper,
    AssessmentQuestion,
    AssessmentReport,
    AssessmentResult,
    LearningRecord,
)
from app.models.assessment import (
    PAPER_ACTIVE,
    QUESTION_TEXT,
    REPORT_CAREER,
)
from app.models.learning import ACTION_SUBMIT, MODULE_ASSESSMENT
from app.models.user import User
from app.schemas.assessment import (
    AnswerItemIn,
    AssessmentResultOut,
    AssessmentSubmitIn,
    AssessmentSubmitOut,
    PaperOut,
    QuestionOptionOut,
    QuestionOut,
    RadarPointOut,
    RecommendedJobOut,
    ScaleSpecOut,
    SkillGapOut,
)
from app.schemas.common import ApiResponse
from app.services.assessment_scoring import (
    DIMENSION_LABELS,
    aggregate_dimension_scores,
    build_radar_data,
    score_question,
    total_score,
)
from app.services.career_recommender import recommend_jobs

router = APIRouter(prefix="/assessment", tags=["assessment"])


# -------------------------------------------------------------------- #
# 试卷 / 题目
# -------------------------------------------------------------------- #
@router.get(
    "/papers",
    response_model=ApiResponse[List[PaperOut]],
    summary="可用测评试卷列表",
)
def list_papers(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """返回状态为 active 的试卷（含题目数量）。"""
    rows = db.execute(
        select(AssessmentPaper, func.count(AssessmentQuestion.id))
        .outerjoin(
            AssessmentQuestion,
            AssessmentQuestion.paper_id == AssessmentPaper.id,
        )
        .where(AssessmentPaper.status == PAPER_ACTIVE)
        .group_by(AssessmentPaper.id)
        .order_by(AssessmentPaper.id.asc())
    ).all()

    papers = [
        PaperOut(
            id=paper.id,
            title=paper.title,
            description=paper.description,
            type=paper.type,
            status=paper.status,
            question_count=int(count),
            created_at=paper.created_at.isoformat() if paper.created_at else "",
        )
        for paper, count in rows
    ]
    return success(papers)


@router.get(
    "/questions",
    response_model=ApiResponse[List[QuestionOut]],
    summary="获取试卷题目",
)
def get_questions(
    paper_id: int = Query(..., ge=1, description="试卷ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """按题序返回题目（选项/量表参数下发，评分规则不下发）。"""
    paper = db.get(AssessmentPaper, paper_id)
    if paper is None or paper.status != PAPER_ACTIVE:
        raise HTTPException(status_code=404, detail="试卷不存在或已下线")

    questions = db.scalars(
        select(AssessmentQuestion)
        .where(AssessmentQuestion.paper_id == paper_id)
        .order_by(AssessmentQuestion.order_no.asc(), AssessmentQuestion.id.asc())
    ).all()

    return success([_to_question_out(q) for q in questions])


def _to_question_out(q: AssessmentQuestion) -> QuestionOut:
    """题目出参：剥离评分规则，仅保留展示信息。"""
    options = None
    scale = None
    placeholder = None

    rule = q.score_rule or {}
    opt_json = q.options_json or {}
    if q.question_type in ("single", "multiple"):
        options = [
            QuestionOptionOut(key=str(k), label=str(v))
            for k, v in opt_json.items()
        ]
    elif q.question_type == "scale":
        options = [
            QuestionOptionOut(key=str(k), label=str(v))
            for k, v in opt_json.items()
        ]
        scale = ScaleSpecOut(
            min=int(rule.get("min", 1)),
            max=int(rule.get("max", 5)),
            step=int(rule.get("step", 1)),
            labels=[str(v) for v in opt_json.values()] or None,
        )
    elif q.question_type == QUESTION_TEXT:
        placeholder = str(rule.get("placeholder") or "请输入你的真实想法（无标准答案）")

    return QuestionOut(
        id=q.id,
        paper_id=q.paper_id,
        question_type=q.question_type,
        content=q.content,
        dimension=q.dimension,
        dimension_label=DIMENSION_LABELS.get(q.dimension, q.dimension),
        order_no=q.order_no,
        options=options,
        scale=scale,
        placeholder=placeholder,
    )


# -------------------------------------------------------------------- #
# 提交测评
# -------------------------------------------------------------------- #
@router.post(
    "/submit",
    response_model=ApiResponse[AssessmentSubmitOut],
    summary="提交测评答卷",
    description="服务端逐题规则评分 → 维度聚合 → 职业推荐,结果落库。",
)
def submit_assessment(
    payload: AssessmentSubmitIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """提交答卷：逐题评分、维度聚合、职业推荐、结果与报告落库。"""
    paper = db.get(AssessmentPaper, payload.paper_id)
    if paper is None or paper.status != PAPER_ACTIVE:
        raise HTTPException(status_code=404, detail="试卷不存在或已下线")

    questions = db.scalars(
        select(AssessmentQuestion)
        .where(AssessmentQuestion.paper_id == paper.id)
        .order_by(AssessmentQuestion.order_no.asc(), AssessmentQuestion.id.asc())
    ).all()
    q_by_id = {q.id: q for q in questions}

    answer_map = {item.question_id: item.answer for item in payload.answers}
    scores: List[float] = []
    for q in questions:
        raw = answer_map.get(q.id)
        if raw is None:
            raise HTTPException(
                status_code=400,
                detail="题目(id={})未作答，请完成全部题目后再提交".format(q.id),
            )
        score = score_question(q, raw)
        scores.append(score)
        db.add(
            AssessmentAnswer(
                user_id=user.id,
                paper_id=paper.id,
                question_id=q.id,
                answer_json={"value": raw},
                score=score,
            )
        )

    dimension_scores = aggregate_dimension_scores(questions, scores)
    total = total_score(dimension_scores)
    radar = build_radar_data(dimension_scores)
    recomm = recommend_jobs(dimension_scores)

    result = AssessmentResult(
        user_id=user.id,
        paper_id=paper.id,
        total_score=total,
        dimension_scores_json=dimension_scores,
        recommended_jobs_json=recomm,
    )
    db.add(result)
    db.flush()  # 获得 result.id

    # 同步写一条职业测评报告（模块2 报告历史页可查）
    db.add(
        AssessmentReport(
            user_id=user.id,
            assessment_id=paper.id,
            report_type=REPORT_CAREER,
            report_json={
                "paper_title": paper.title,
                "total_score": total,
                "dimension_scores": dimension_scores,
                "radar_data": radar,
                "recommendation": recomm,
                "result_id": result.id,
            },
        )
    )
    # 学习轨迹流水（断点续学 / 统计用途）
    db.add(
        LearningRecord(
            user_id=user.id,
            module_type=MODULE_ASSESSMENT,
            action_type=ACTION_SUBMIT,
            target_id=paper.id,
            duration=payload.duration or 0,
            result={"result_id": result.id, "total_score": total},
        )
    )

    # 业务闭环2：自动触发画像生成 + 推荐岗位（规则路径，同步同事物）
    from app.services.persona_auto import auto_build_persona, sync_target_job_to_archive

    persona = auto_build_persona(db, user.id)
    if persona is not None:
        sync_target_job_to_archive(db, user.id, persona.target_job)

    db.commit()

    jobs = recomm.get("jobs", [])
    return success(
        AssessmentSubmitOut(
            result_id=result.id,
            total_score=total,
            top_job=jobs[0]["job_name"] if jobs else None,
        )
    )


# -------------------------------------------------------------------- #
# 结果详情
# -------------------------------------------------------------------- #
@router.get(
    "/result/{result_id}",
    response_model=ApiResponse[AssessmentResultOut],
    summary="测评结果详情",
)
def get_result(
    result_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """返回测评结果：总分 / 维度分 / 雷达图 / 职业推荐 / 技能差距。"""
    result = db.get(AssessmentResult, result_id)
    if result is None or result.user_id != user.id:
        raise HTTPException(status_code=404, detail="测评结果不存在")

    paper = db.get(AssessmentPaper, result.paper_id)
    dim_scores = result.dimension_scores_json or {}
    recomm = result.recommended_jobs_json or {"source": "rule", "jobs": []}
    radar = build_radar_data(dim_scores)
    raw_jobs = recomm.get("jobs", [])
    recommended = [
        RecommendedJobOut(
            job_id=j.get("job_id", ""),
            job_name=j.get("job_name", ""),
            summary=j.get("summary", ""),
            match_score=float(j.get("match_score", 0)),
            reason=j.get("reason", ""),
            skill_gaps=[
                SkillGapOut(
                    skill=g.get("skill", ""),
                    dimension=g.get("dimension", ""),
                    current=float(g.get("current", 0)),
                    threshold=float(g.get("threshold", 0)),
                    gap=float(g.get("gap", 0)),
                )
                for g in (j.get("skill_gaps") or [])
            ],
        )
        for j in raw_jobs
    ]

    return success(
        AssessmentResultOut(
            id=result.id,
            paper_id=result.paper_id,
            paper_title=paper.title if paper else "",
            total_score=result.total_score,
            dimension_scores=dim_scores,
            dimension_labels=DIMENSION_LABELS,
            radar_data={"dimensions": radar["dimensions"]},
            recommended_jobs=recommended,
            recommendation_source=recomm.get("source", "rule"),
            created_at=result.created_at.isoformat() if result.created_at else "",
        )
    )