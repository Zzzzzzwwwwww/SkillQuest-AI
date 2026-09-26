"""
SkillQuest AI 学习评估复盘 —— 规则服务（模块7）

原则（第1条）：总分、得分率、知识点掌握度、雷达、趋势、薄弱识别全部规则计算，
Assessment Agent 不参与任何数值计算（仅报告生成时做解读增强）。

核心能力：
  - start_exam / submit_exam：试卷答题闭环与规则评分、掌握度 upsert
  - build_exam_result：结果详情（题目对错 / 掌握度 / 能力雷达 / 趋势 / 薄弱点 / 下一步）
  - get_mastery：掌握度总览（含热力图矩阵）
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment_review import (
    ExamAnswer,
    ExamQuestion,
    ExamRecord,
    KnowledgeMastery,
    StageExam,
    QT_JUDGE,
    QT_MULTIPLE,
    QT_SINGLE,
    RECORD_PENDING,
    RECORD_SUBMITTED,
)
from app.models.learning_path import LearningResource
from app.models.skill import SkillNode

# 掌握度阈值（与技能图谱模块一致）
MASTERY_STRONG = 70      # 优势
MASTERY_WEAK = 60        # 薄弱
PASS_SCORE = 60          # 及格线

# 资源类型 → 下一步建议文案
_NEXT_STEP_TPL = "优先复习「{name}」（当前掌握度 {score} 分），可从 {kind}「{title}」开始。"


def _norm(raw: Any) -> str:
    """答案归一化：strip + 小写 + 去空格。"""
    if isinstance(raw, bool):
        return str(raw).lower()
    return str(raw).strip().lower().replace(" ", "")


def is_answer_correct(question_type: str, correct_answer: Any, user_answer: Any) -> bool:
    """规则判定对错：单选比较 key；多选比较集合；判断比较布尔。"""
    if question_type == QT_MULTIPLE:
        try:
            cset: Set[str] = {_norm(x) for x in (correct_answer or [])}
            uset: Set[str] = {_norm(x) for x in (user_answer or [])}
        except TypeError:
            return False
        return bool(cset) and cset == uset
    if question_type == QT_JUDGE:
        return _norm(correct_answer) == _norm(user_answer)
    # 单选 / 默认
    return _norm(correct_answer) == _norm(user_answer)


def _points_for(questions: List[ExamQuestion], question_id: int) -> int:
    for q in questions:
        if q.id == question_id:
            return q.score
    return 0


def start_exam(db: Session, user_id: int, exam_id: int) -> ExamRecord:
    """创建一条测评记录（pending）。"""
    record = ExamRecord(
        user_id=user_id,
        exam_id=exam_id,
        score=0,
        start_time=datetime.utcnow(),
        status=RECORD_PENDING,
    )
    db.add(record)
    db.flush()
    return record


def submit_exam(
    db: Session,
    user_id: int,
    record_id: int,
    answers: List[Dict[str, Any]],
) -> ExamRecord:
    """提交评分：逐题判定 → 分数汇总 → 掌握度 upsert → 记录落库。"""
    record = db.get(ExamRecord, record_id)
    if record is None or record.user_id != user_id:
        raise ValueError("测评记录不存在或无权操作")
    if record.status == RECORD_SUBMITTED:
        raise ValueError("该测评已提交，不可重复提交")

    questions = db.scalars(
        select(ExamQuestion).where(ExamQuestion.exam_id == record.exam_id)
    ).all()
    question_map = {q.id: q for q in questions}

    total_earned = 0
    total_points = sum(q.score for q in questions)
    correct_count = 0
    answer_map: Dict[int, Dict[str, Any]] = {a["question_id"]: a for a in answers}

    scored: List[ExamAnswer] = []
    for q in questions:
        a = answer_map.get(q.id)
        user_answer = a["user_answer"] if a else None
        ok = is_answer_correct(q.question_type, q.answer, user_answer)
        earned = q.score if ok else 0
        total_earned += earned
        if ok:
            correct_count += 1
        scored.append(
            ExamAnswer(
                record_id=record.id,
                question_id=q.id,
                user_answer=str(user_answer) if user_answer is not None else "",
                is_correct=ok,
                score=earned,
            )
        )

    percent = round(total_earned * 100 / total_points) if total_points else 0
    record.score = percent
    record.submit_time = datetime.utcnow()
    record.status = RECORD_SUBMITTED

    db.add_all(scored)
    _upsert_masteries(db, user_id, record, questions, answer_map)
    # 业务闭环4：掌握度 → 技能图谱状态联动 + 弱点诊断落库
    _sync_user_skill_status(db, user_id, questions, answer_map)
    _upsert_weakness_diagnostics(db, user_id, record, questions)
    db.flush()
    return record


def _upsert_masteries(
    db: Session,
    user_id: int,
    record: ExamRecord,
    questions: List[ExamQuestion],
    answer_map: Dict[int, Dict[str, Any]],
) -> None:
    """按知识点聚合本次得分率并滚动更新掌握度（加权平均 + 复审计数）。"""
    kp_stats: Dict[int, List[int]] = {}
    for q in questions:
        if not q.knowledge_point_id:
            continue
        a = answer_map.get(q.id)
        ok = is_answer_correct(q.question_type, q.answer, a["user_answer"] if a else None)
        rate = q.score if ok else 0
        kp_stats.setdefault(q.knowledge_point_id, []).append(rate / q.score if q.score else 0)

    now = datetime.utcnow()
    for kp_id, rates in kp_stats.items():
        avg_rate = round(sum(rates) * 100 / len(rates))
        m = db.scalar(
            select(KnowledgeMastery).where(
                KnowledgeMastery.user_id == user_id,
                KnowledgeMastery.knowledge_point_id == kp_id,
            )
        )
        if m is None:
            db.add(
                KnowledgeMastery(
                    user_id=user_id,
                    knowledge_point_id=kp_id,
                    mastery_score=avg_rate,
                    last_test_time=now,
                    review_count=1,
                )
            )
        else:
            merged = round((m.mastery_score * m.review_count + avg_rate) / (m.review_count + 1))
            m.mastery_score = merged
            m.last_test_time = now
            m.review_count = m.review_count + 1


# -------------------------------------------------------------------- #
# 业务闭环4：掌握度 → 技能图谱状态联动 + 弱点诊断
# -------------------------------------------------------------------- #
def _sync_user_skill_status(
    db: Session,
    user_id: int,
    questions: List[ExamQuestion],
    answer_map: Dict[int, Dict[str, Any]],
) -> None:
    """把本次阶段测评的掌握度联动到技能图谱 user_skill_status。

    - 知识节点：mastery = 本卷在该知识点的得分率（与 knowledge_mastery 一致）
    - 技能节点：mastery = 其下知识节点 mastery 均值（仅覆盖被考核的知识点），状态随阈值
    """
    if not questions:
        return
    kp_ids = {q.knowledge_point_id for q in questions if q.knowledge_point_id}
    if not kp_ids:
        return

    from app.models.skill import SkillNode, STATUS_LEARNING, STATUS_MASTERED, UserSkillStatus

    nodes = db.scalars(select(SkillNode).where(SkillNode.id.in_(kp_ids))).all()
    node_map = {n.id: n for n in nodes}
    skill_ids = {n.parent_id for n in nodes if n.parent_id}

    existing = {
        r.skill_node_id: r
        for r in db.scalars(
            select(UserSkillStatus).where(UserSkillStatus.user_id == user_id)
        ).all()
    }

    updated_kp: Dict[int, int] = {}

    def _status_of(mastery: int) -> str:
        return STATUS_MASTERED if mastery >= 80 else (STATUS_LEARNING if mastery > 0 else "not_started")

    for n in nodes:
        kp_score = round(
            sum(
                100
                for q in questions
                if q.knowledge_point_id == n.id
                and (a := answer_map.get(q.id)) is not None
                and is_answer_correct(q.question_type, q.answer, a.get("user_answer"))
            )
            * 100
            / max(1, sum(1 for q in questions if q.knowledge_point_id == n.id))
        )
        row = existing.get(n.id)
        if row is None:
            row = UserSkillStatus(user_id=user_id, skill_node_id=n.id)
            db.add(row)
        row.mastery_score = max(row.mastery_score or 0, kp_score)
        row.status = _status_of(row.mastery_score)
        db.add(row)
        updated_kp[n.id] = row.mastery_score

    for sid in skill_ids:
        bkps = [
            v
            for kp_id, v in updated_kp.items()
            if (parent := node_map.get(kp_id)) is not None
            and parent.parent_id == sid
        ]
        if not bkps:
            continue
        avg = round(sum(bkps) / len(bkps))
        row = existing.get(sid)
        if row is None:
            row = UserSkillStatus(user_id=user_id, skill_node_id=sid)
            db.add(row)
        row.mastery_score = max(row.mastery_score or 0, avg)
        row.status = _status_of(row.mastery_score)
        db.add(row)


def _upsert_weakness_diagnostics(
    db: Session,
    user_id: int,
    record: ExamRecord,
    questions: List[ExamQuestion],
) -> None:
    """弱点诊断落库：本卷覆盖知识点中掌握度 < MASTERY_WEAK(60) 的生成诊断。

    - 同一测评记录重建（保证诊断与最新结果一致）
    - 后续 AI 导师按 status != treated 推送
    """
    if not questions:
        return

    from sqlalchemy import delete

    from app.models.business_loop import WeaknessDiagnostic
    from app.models.skill import SkillNode

    db.execute(
        delete(WeaknessDiagnostic).where(
            WeaknessDiagnostic.user_id == user_id,
            WeaknessDiagnostic.record_id == record.id,
        )
    )

    kp_ids = {q.knowledge_point_id for q in questions if q.knowledge_point_id}
    if not kp_ids:
        db.flush()
        return

    # 会话 autoflush=False，需手动 flush 使 _upsert_masteries 新增的掌握度可见
    db.flush()

    mastery_rows = db.scalars(
        select(KnowledgeMastery).where(
            KnowledgeMastery.user_id == user_id,
            KnowledgeMastery.knowledge_point_id.in_(kp_ids),
        )
    ).all()
    m_map = {m.knowledge_point_id: m for m in mastery_rows}

    nodes = db.scalars(select(SkillNode).where(SkillNode.id.in_(kp_ids))).all()
    node_map = {n.id: n for n in nodes}
    skill_map = {
        s.id: s
        for s in db.scalars(
            select(SkillNode).where(SkillNode.id.in_({n.parent_id for n in nodes if n.parent_id}))
        ).all()
    }

    kp_chain = _kp_chain(db)
    diag_rows = 0
    for kp_id in sorted(kp_ids):
        m = m_map.get(kp_id)
        if m is None or m.mastery_score >= MASTERY_WEAK:
            continue
        node = node_map.get(kp_id)
        parent = skill_map.get(node.parent_id) if node else None
        domain = parent.name if parent else ""
        meta = kp_chain.get(kp_id, {"name": node.name if node else f"知识点#{kp_id}"})
        db.add(
            WeaknessDiagnostic(
                user_id=user_id,
                record_id=record.id,
                knowledge_point_id=kp_id,
                kp_name=meta["name"],
                domain=domain,
                mastery_score=m.mastery_score,
                diagnosis=(
                    f"该知识点掌握度仅 {m.mastery_score} 分（阈值 80），"
                    f"本次测评中相关题目失分。建议结合「AI 导师」提问讲解，"
                    f"并完成对应 {domain} 领域的专项练习后再测。"
                ),
                status="new",
            )
        )
        diag_rows += 1
    db.flush()
    return diag_rows


# -------------------------------------------------------------------- #
# 结果聚合
# -------------------------------------------------------------------- #
def _kp_chain(db: Session) -> Dict[int, Dict[str, Any]]:
    """知识点 → {name, domain}（knowledge → skill → capability 链路，无父级归入其他）。"""
    nodes = db.scalars(select(SkillNode)).all()
    node_map = {n.id: n for n in nodes}
    result: Dict[int, Dict[str, Any]] = {}
    for n in nodes:
        if n.node_type != "knowledge":
            continue
        name = n.name
        domain = "其他"
        skill = node_map.get(n.parent_id) if n.parent_id else None
        if skill is not None:
            domain = skill.name
            cap = node_map.get(skill.parent_id) if skill.parent_id else None
            if cap is not None:
                domain = f"{cap.name}·{skill.name}"
        result[n.id] = {"name": name, "domain": domain}
    return result


def _domain_scores(mastery_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按能力域聚合掌握度均值（雷达图数据）。"""
    bucket: Dict[str, List[int]] = {}
    for it in mastery_items:
        bucket.setdefault(it["domain"] or "其他", []).append(it["mastery_score"])
    radar = [
        {"domain": domain, "value": round(sum(v) / len(v))}
        for domain, v in sorted(bucket.items(), key=lambda x: -sum(x[1]) / len(x[1]))
    ]
    return radar


def build_exam_result(db: Session, user_id: int, record_id: int) -> Dict[str, Any]:
    """构建测评结果详情。"""
    record = db.get(ExamRecord, record_id)
    if record is None or record.user_id != user_id:
        raise ValueError("测评记录不存在或无权查看")

    exam = db.get(StageExam, record.exam_id)
    questions = db.scalars(
        select(ExamQuestion).where(ExamQuestion.exam_id == record.exam_id).order_by(ExamQuestion.id)
    ).all()
    q_map = {q.id: q for q in questions}
    answers = db.scalars(
        select(ExamAnswer).where(ExamAnswer.record_id == record_id)
    ).all()
    a_map = {a.question_id: a for a in answers}

    q_result: List[Dict[str, Any]] = []
    for q in questions:
        a = a_map.get(q.id)
        q_result.append(
            {
                "question_id": q.id,
                "content": q.content,
                "is_correct": bool(a.is_correct) if a else False,
                "points_earned": a.score if a else 0,
                "points_total": q.score,
                "correct_answer": q.answer,
                "user_answer": a.user_answer if a else None,
            }
        )

    kp_chain = _kp_chain(db)
    mastery_rows = db.scalars(
        select(KnowledgeMastery).where(KnowledgeMastery.user_id == user_id)
    ).all()
    m_map = {m.knowledge_point_id: m for m in mastery_rows}

    mastery_items: List[Dict[str, Any]] = []
    for kp_id, m in m_map.items():
        meta = kp_chain.get(kp_id, {"name": f"知识点#{kp_id}", "domain": "其他"})
        mastery_items.append(
            {
                "knowledge_point_id": kp_id,
                "name": meta["name"],
                "domain": meta["domain"],
                "mastery_score": m.mastery_score,
                "last_test_time": m.last_test_time.isoformat() if m.last_test_time else None,
                "review_count": m.review_count,
            }
        )
    mastery_items.sort(key=lambda x: x["mastery_score"])

    # 本次试卷涉及的知识点集合（用于标识薄弱排序）
    exam_kp_ids = {q.knowledge_point_id for q in questions if q.knowledge_point_id}
    weak = [
        {
            "knowledge_point_id": it["knowledge_point_id"],
            "name": it["name"],
            "mastery_score": it["mastery_score"],
            "suggestion": "",
        }
        for it in mastery_items
        if it["mastery_score"] < MASTERY_WEAK and it["knowledge_point_id"] in exam_kp_ids
    ] or [
        {
            "knowledge_point_id": it["knowledge_point_id"],
            "name": it["name"],
            "mastery_score": it["mastery_score"],
            "suggestion": "",
        }
        for it in mastery_items
        if it["mastery_score"] < MASTERY_WEAK
    ]

    # 学习趋势（历史已提交测评）
    records = db.scalars(
        select(ExamRecord)
        .where(
            ExamRecord.user_id == user_id,
            ExamRecord.status == RECORD_SUBMITTED,
        )
        .order_by(ExamRecord.submit_time.asc())
    ).all()
    trend = []
    for r in records:
        e = db.get(StageExam, r.exam_id)
        trend.append(
            {
                "record_id": r.id,
                "exam_title": e.title if e else f"测评#{r.exam_id}",
                "score": r.score,
                "submitted_at": r.submit_time.isoformat() if r.submit_time else "",
            }
        )

    next_steps = _build_next_steps(db, weak)
    for it in weak:
        it["suggestion"] = f"掌握度偏低（{it['mastery_score']} 分），建议复习后再测。"
    for n in next_steps:
        pass

    return {
        "record_id": record.id,
        "exam_id": record.exam_id,
        "exam_title": exam.title if exam else "",
        "stage": exam.stage if exam else "",
        "score": record.score,
        "correct_count": sum(1 for qr in q_result if qr["is_correct"]),
        "total_count": len(q_result),
        "submitted_at": record.submit_time.isoformat() if record.submit_time else "",
        "questions": q_result,
        "mastery": mastery_items,
        "radar": _domain_scores(mastery_items),
        "trend": trend,
        "weak_points": weak,
        "next_steps": next_steps,
    }


def _build_next_steps(db: Session, weak_points: List[Dict[str, Any]]) -> List[str]:
    """为薄弱知识点推荐下一步：关联学习资源（视频/课程/练习）优先。"""
    steps: List[str] = []
    for w in weak_points[:3]:
        kp_id = w["knowledge_point_id"]
        if not kp_id:
            continue
        res = db.scalars(
            select(LearningResource)
            .where(LearningResource.skill_node_id == kp_id)
            .order_by(LearningResource.id.asc())
            .limit(1)
        ).first()
        if res is not None:
            steps.append(_NEXT_STEP_TPL.format(name=w["name"], score=w["mastery_score"], kind=res.type, title=res.title))
        else:
            steps.append(f"针对「{w['name']}」做专项练习并复盘错题。")
    if not steps:
        steps.append("当前无明显薄弱点，继续按冒险路径推进学习即可。")
    return steps


# -------------------------------------------------------------------- #
# 掌握度总览（含热力图）
# -------------------------------------------------------------------- #
def get_mastery(db: Session, user_id: int) -> Dict[str, Any]:
    """掌握度总览：条目列表 + 热力图矩阵（能力域×知识点，值=掌握度）。"""
    rows = db.scalars(
        select(KnowledgeMastery).where(KnowledgeMastery.user_id == user_id)
    ).all()
    if not rows:
        return {"items": [], "heatmap": {"domains": [], "points": []}}

    kp_chain = _kp_chain(db)
    items: List[Dict[str, Any]] = []
    for m in rows:
        meta = kp_chain.get(m.knowledge_point_id, {"name": f"知识点#{m.knowledge_point_id}", "domain": "其他"})
        items.append(
            {
                "knowledge_point_id": m.knowledge_point_id,
                "name": meta["name"],
                "domain": meta["domain"],
                "mastery_score": m.mastery_score,
                "last_test_time": m.last_test_time.isoformat() if m.last_test_time else None,
                "review_count": m.review_count,
            }
        )

    # 热力图点：domain 作为 x 行、知识点作为 y 列（ECharts heatmap data 格式）
    domains: List[str] = []
    points: List[Dict[str, Any]] = []
    for it in items:
        d = it["domain"]
        if d not in domains:
            domains.append(d)
        points.append({"domain": it["domain"], "name": it["name"], "value": it["mastery_score"]})

    return {
        "items": items,
        "heatmap": {
            "domains": domains,
            "points": points,
        },
    }