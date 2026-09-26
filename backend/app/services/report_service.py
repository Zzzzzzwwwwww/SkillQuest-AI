"""
SkillQuest AI 学习评估复盘 —— 报告服务（模块7）

- 规则引擎：总分/优势/薄弱/建议/下一步均基于计算数据生成模板文案
- Assessment Agent 增强：LLM 配置时对测评做解读（summary/domain_analysis/改进计划），
  未配置自动降级为规则文案，前端展示 ai_enriched 标记
- PDF 导出：reportlab + UnicodeCIDFont(STSong-Light) 生成中文 PDF（零外部字体）
"""

import asyncio
import io
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment_review import (
    ExamRecord,
    LearningReport,
    RECORD_SUBMITTED,
    REPORT_EXAM,
)
from app.services.agent_service import AgentInput, agent_service
from app.services.exam_service import (
    MASTERY_STRONG,
    MASTERY_WEAK,
    _kp_chain,
    _domain_scores,
    build_exam_result,
)


def _latest_submitted_record(db: Session, user_id: int, record_id: Optional[int] = None) -> ExamRecord:
    if record_id is not None:
        record = db.get(ExamRecord, record_id)
        if record is None or record.user_id != user_id or record.status != RECORD_SUBMITTED:
            raise ValueError("测评记录不存在或无权查看")
        return record
    record = db.scalars(
        select(ExamRecord)
        .where(ExamRecord.user_id == user_id, ExamRecord.status == RECORD_SUBMITTED)
        .order_by(ExamRecord.submit_time.desc())
        .limit(1)
    ).first()
    if record is None:
        raise ValueError("暂无已完成的测评，请先完成一次阶段测评")
    return record


def build_rule_report(db: Session, user_id: int, record: ExamRecord) -> Dict[str, Any]:
    """规则化报告主体（分数/优势/薄弱/建议/下一步/可视化数据）。"""
    result = build_exam_result(db, user_id, record.id)
    score = result["score"]
    mastery = result["mastery"]
    strong = [m for m in mastery if m["mastery_score"] >= MASTERY_STRONG]
    weak = result["weak_points"]

    if score >= 90:
        overall = f"本次阶段测评表现优异，得分 {score} 分，掌握扎实，可以进入下一阶段挑战。"
    elif score >= PASS_MSG_SCORE:
        overall = f"本次阶段测评得分 {score} 分，整体掌握良好，但仍有提升空间。"
    else:
        overall = f"本次阶段测评得分 {score} 分，存在明显薄弱环节，建议按报告建议重点补强。"
    overall += f" 共 {result['total_count']} 题，答对 {result['correct_count']} 题。"

    strengths = [{"name": m["name"], "score": m["mastery_score"]} for m in strong]
    weaknesses = [
        {
            "knowledge_point_id": w["knowledge_point_id"],
            "name": w["name"],
            "mastery_score": w["mastery_score"],
        }
        for w in weak
    ]

    if weaknesses:
        suggestion = (
            "优先复习薄弱知识点，并做针对性练习；采用间隔重复复习（建议 1/3/7 天回顾），"
            "结合「AI 导师」就薄弱点提问刨根问底。"
        )
    else:
        suggestion = "当前阶段掌握度良好，建议进入下一段位挑战，并保持每周一次复盘测评。"

    next_steps = result["next_steps"]

    return {
        "record_id": result["record_id"],
        "exam_title": result["exam_title"],
        "stage": result["stage"],
        "score": score,
        "overall": overall,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suggestion": suggestion,
        "next_steps": next_steps,
        "radar": result["radar"],
        "trend": result["trend"],
        "mastery": mastery,
        "mastered_count": len(strong),
        "weak_count": len(weaknesses),
    }


PASS_MSG_SCORE = 60


def _assess_with_agent(rule_report: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """调用 Assessment Agent（统一 AgentService）做解读增强；未配置/失败返回 None。

    降级策略：模型未配置或调用失败时返回 None，由调用方沿用规则文案，ai_enriched=False。
    """
    payload = {
        "exam_title": rule_report.get("exam_title", ""),
        "stage": rule_report.get("stage", ""),
        "score": rule_report.get("score", 0),
        "domain_analysis": [
            {"knowledge": m["name"], "mastery_level": m["mastery_score"]}
            for m in rule_report.get("mastery", [])
        ],
        "wrong_questions": self_the_wrongs(rule_report),
    }

    async def _call() -> Optional[Dict[str, Any]]:
        result = await agent_service.run(
            AgentInput(
                agent_type="assessment",
                user_context=payload,
                max_tokens=1024,
            )
        )
        if result.degraded or not result.ok or not result.data:
            return None
        return result.data

    try:
        return asyncio.run(_call())
    except Exception:  # noqa: BLE001
        return None


def self_the_wrongs(rule_report: Dict[str, Any]) -> list:
    """从规则报告中的薄弱点生成错题要点（供 Agent 归因，不编造分数）。"""
    return [
        {"knowledge": w["name"], "mastery_level": w["mastery_score"]}
        for w in rule_report.get("weaknesses", [])
    ]


def generate_report(
    db: Session, user_id: int, record_id: Optional[int] = None, report_type: str = REPORT_EXAM
) -> Dict[str, Any]:
    """生成并持久化学习报告（Assessment Agent 可选增强）。"""
    record = _latest_submitted_record(db, user_id, record_id)
    report = build_rule_report(db, user_id, record)

    ai_enriched = False
    agent = None
    if report_type == REPORT_EXAM:
        agent = _assess_with_agent(report)
        if agent:
            ai_enriched = True
            upgraded = report.copy()
            upgraded["summary"] = agent.get("summary", report["overall"])
            upgraded["domain_analysis"] = agent.get("domain_analysis", [])
            upgraded["mistake_patterns"] = agent.get("mistake_patterns", [])
            upgraded["improvement_plan"] = agent.get("improvement_plan", report["suggestion"])
            upgraded["next_focus"] = agent.get("next_focus", [])
            report = upgraded

    row = LearningReport(
        user_id=user_id,
        report_type=report_type,
        report_json=report,
    )
    db.add(row)
    db.flush()
    return {
        "id": row.id,
        "report_type": row.report_type,
        "report_json": report,
        "ai_enriched": ai_enriched,
        "pdf_url": None,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


def get_report(db: Session, user_id: int, report_id: int) -> Dict[str, Any]:
    row = db.get(LearningReport, report_id)
    if row is None or row.user_id != user_id:
        raise ValueError("报告不存在或无权查看")
    return {
        "id": row.id,
        "report_type": row.report_type,
        "report_json": row.report_json,
        "pdf_url": row.pdf_url,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


def list_reports(db: Session, user_id: int) -> list:
    rows = db.scalars(
        select(LearningReport)
        .where(LearningReport.user_id == user_id)
        .order_by(LearningReport.created_at.desc())
    ).all()
    return [
        {
            "id": r.id,
            "report_type": r.report_type,
            "score": (r.report_json or {}).get("score"),
            "exam_title": (r.report_json or {}).get("exam_title"),
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


# -------------------------------------------------------------------- #
# PDF 导出
# -------------------------------------------------------------------- #
def _build_pdf(report: LearningReport) -> bytes:
    """reportlab 生成中文 PDF（UnicodeCIDFont STSong-Light，免字体文件）。"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import (ListFlowable, ListItem, Paragraph,
                                    SimpleDocTemplate, Spacer)

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    CJK = "STSong-Light"
    title_style = ParagraphStyle("t", fontName=CJK, fontSize=18, leading=24, spaceAfter=10)
    h_style = ParagraphStyle("h", fontName=CJK, fontSize=13, leading=18, spaceBefore=8, spaceAfter=4)
    body = ParagraphStyle("b", fontName=CJK, fontSize=10.5, leading=16, textColor="#333333")
    small = ParagraphStyle("s", fontName=CJK, fontSize=9.5, leading=14, textColor="#666666")

    data = report.report_json or {}
    stage_label = {"bronze": "青铜", "silver": "白银", "gold": "黄金",
                   "platinum": "铂金", "diamond": "钻石", "king": "王者"}
    flow: list = [
        Paragraph(f"SkillQuest AI 学习评估报告", title_style),
        Paragraph(f"试卷：{data.get('exam_title', '')}　·　阶段：{stage_label.get(data.get('stage', ''), data.get('stage', ''))}　·　生成时间 {datetime.utcnow():%Y-%m-%d %H:%M}", small),
        Spacer(1, 6 * mm),
        Paragraph(f"本次得分：{data.get('score', 0)} 分　|　优势知识点 {data.get('mastered_count', 0)} 个　|　薄弱点 {data.get('weak_count', 0)} 个", h_style),
    ]

    flow.append(Paragraph("一、总体评价", h_style))
    flow.append(Paragraph(str(data.get("overall", "")), body))

    flow.append(Paragraph("二、优势", h_style))
    st = data.get("strengths", [])
    flow.append(ListFlowable(
        [ListItem(Paragraph(f"{s.get('name', '')}（掌握度 {s.get('score', 0)} 分）", body), bulletType="bullet")
         for s in st] or [Paragraph("暂无", body)],
        bulletType="bullet"))

    flow.append(Paragraph("三、薄弱点", h_style))
    wk = data.get("weaknesses", [])
    flow.append(ListFlowable(
        [ListItem(Paragraph(f"{w.get('name', '')}（掌握度 {w.get('mastery_score', 0)} 分）", body), bulletType="bullet")
         for w in wk] or [Paragraph("暂无", body)],
        bulletType="bullet"))

    flow.append(Paragraph("四、学习建议", h_style))
    flow.append(Paragraph(str(data.get("suggestion", "")), body))

    flow.append(Paragraph("五、下一步任务", h_style))
    flow.append(ListFlowable(
        [ListItem(Paragraph(str(n), body), bulletType="bullet")
         for n in (data.get("next_steps") or [])],
        bulletType="bullet"))

    if data.get("trend"):
        flow.append(Paragraph("六、学习趋势（历次测评得分）", h_style))
        trend_text = " → ".join(f"{t.get('exam_title', '')}:{t.get('score', 0)} 分" for t in data["trend"])
        flow.append(Paragraph(trend_text, small))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
    )
    doc.build(flow)
    return buf.getvalue()


def export_report_pdf(db: Session, user_id: int, report_id: Optional[int] = None) -> bytes:
    """导出报告 PDF；缺省取该用户最新报告。"""
    if report_id is not None:
        row = db.get(LearningReport, report_id)
        if row is None or row.user_id != user_id:
            raise ValueError("报告不存在或无权导出")
    else:
        row = db.scalars(
            select(LearningReport)
            .where(LearningReport.user_id == user_id)
            .order_by(LearningReport.created_at.desc())
            .limit(1)
        ).first()
        if row is None:
            raise ValueError("暂无报告可导出，请先生成学习报告")
    return _build_pdf(row)