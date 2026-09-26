"""
SkillQuest AI 学习评估复盘接口（模块7）

  - POST /exam/start                 开始测评（返回题目，不下发答案）
  - POST /exam/submit                提交答卷：规则评分 + 掌握度更新
  - GET  /exam/result/{record_id}    结果详情（分数/雷达/知识点/趋势/薄弱/下一步）
  - GET  /mastery                    知识点掌握度总览（热力图）
  - POST /report/generate            学习报告生成（Assessment Agent 可选增强）
  - GET  /report/{id}                报告详情
  - GET  /report/export/pdf          报告 PDF 导出

原则（第1条）：总分/掌握度/薄弱识别全部规则计算，AI 不参与算分。
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.response import success
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.assessment_review import (
    EXAM_ACTIVE,
    RECORD_PENDING,
    RECORD_SUBMITTED,
    StageExam,
)
from app.models.learning import (
    ACTION_FINISH,
    MODULE_ASSESSMENT,
    LearningRecord,
)
from app.models.user import User
from app.schemas.assessment_review import (
    ExamResultOut,
    ExamStartIn,
    ExamStartOut,
    ExamSubmitIn,
    ExamSubmitOut,
    MasteryOut,
    ReportGenerateIn,
    ReportOut,
)
from app.schemas.common import ApiResponse
from app.services.exam_service import (
    build_exam_result,
    get_mastery,
    start_exam,
    submit_exam,
)
from app.services.report_service import (
    export_report_pdf,
    generate_report,
    get_report,
    list_reports,
)

exam_router = APIRouter(prefix="/exam", tags=["exam"])
mastery_router = APIRouter(prefix="/mastery", tags=["mastery"])
report_router = APIRouter(prefix="/report", tags=["report"])


def _question_out(q) -> dict:
    return {
        "id": q.id,
        "question_type": q.question_type,
        "content": q.content,
        "options": q.options_json or [],
        "score": q.score,
        "knowledge_point_id": q.knowledge_point_id,
    }


@exam_router.get(
    "/list",
    include_in_schema=True,
    summary="阶段测评试卷列表",
)
def exam_list(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    exams = db.scalars(
        select(StageExam)
        .where(StageExam.status == EXAM_ACTIVE)
        .order_by(StageExam.id.asc())
    ).all()
    return success(
        [
            {
                "id": e.id,
                "title": e.title,
                "stage": e.stage,
                "description": e.description,
                "total_score": e.total_score,
                "duration": e.duration,
                "status": e.status,
            }
            for e in exams
        ]
    )


@exam_router.post(
    "/start",
    response_model=ApiResponse[ExamStartOut],
    summary="开始阶段测评",
)
def exam_start(
    payload: ExamStartIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    exam = db.get(StageExam, payload.exam_id)
    if exam is None or exam.status != EXAM_ACTIVE:
        raise HTTPException(status_code=404, detail="试卷不存在或未启用")

    record = start_exam(db, user.id, payload.exam_id)
    from app.models.assessment_review import ExamQuestion

    questions = db.scalars(
        select(ExamQuestion)
        .where(ExamQuestion.exam_id == payload.exam_id)
        .order_by(ExamQuestion.id.asc())
    ).all()
    db.commit()
    return success(
        {
            "record_id": record.id,
            "exam_id": exam.id,
            "title": exam.title,
            "stage": exam.stage,
            "description": exam.description,
            "duration": exam.duration,
            "total_score": exam.total_score,
            "end_time": "",
            "questions": [_question_out(q) for q in questions],
        }
    )


@exam_router.post(
    "/submit",
    response_model=ApiResponse[ExamSubmitOut],
    summary="提交测评答卷",
)
def exam_submit(
    payload: ExamSubmitIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        record = submit_exam(
            db,
            user.id,
            payload.record_id,
            [a.model_dump() for a in payload.answers],
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()

    from app.models.assessment_review import ExamAnswer

    answers = db.scalars(
        select(ExamAnswer).where(ExamAnswer.record_id == record.id)
    ).all()
    # 业务闭环4：阶段测评流水打点（学习档案/记录页可查）
    db.add(
        LearningRecord(
            user_id=user.id,
            module_type=MODULE_ASSESSMENT,
            action_type=ACTION_FINISH,
            target_id=record.exam_id,
            duration=0,
            result={
                "record_id": record.id,
                "module": "stage_exam",
                "score": record.score,
                "correct_count": sum(1 for a in answers if a.is_correct),
            },
        )
    )
    db.commit()
    return success(
        {
            "record_id": record.id,
            "score": record.score,
            "correct_count": sum(1 for a in answers if a.is_correct),
            "total_count": len(answers),
            "pass_flag": record.score >= 60,
        }
    )


@exam_router.get(
    "/result/{record_id}",
    response_model=ApiResponse[ExamResultOut],
    summary="测评结果详情",
)
def exam_result(
    record_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = build_exam_result(db, user.id, record_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return success(result)


@mastery_router.get(
    "",
    response_model=ApiResponse[MasteryOut],
    summary="知识点掌握度总览（热力图）",
)
def mastery_overview(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return success(get_mastery(db, user.id))


@report_router.post(
    "/generate",
    response_model=ApiResponse[ReportOut],
    summary="生成学习报告",
)
def report_generate(
    payload: ReportGenerateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = generate_report(
            db, user.id, record_id=payload.record_id, report_type=payload.report_type
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return success(result)


@report_router.get(
    "/export/pdf",
    include_in_schema=True,
    summary="导出报告 PDF",
    description="缺省导出最新报告；?report_id= 指定报告。",
)
def report_export_pdf(
    report_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        data = export_report_pdf(db, user.id, report_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="skillquest-report.pdf"'
        },
    )


@report_router.get(
    "/list",
    include_in_schema=True,
    summary="历史报告列表",
)
def report_list(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return success(list_reports(db, user.id))


@report_router.get(
    "/{report_id}",
    response_model=ApiResponse[ReportOut],
    summary="报告详情",
)
def report_detail(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = get_report(db, user.id, report_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return success(result)