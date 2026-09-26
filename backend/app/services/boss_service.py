"""
SkillQuest AI Boss 挑战服务（模块8 业务闭环6）

完成 Boss 挑战后自动：规则评分 → 发放 XP → 升级等级 → 技能等级/状态更新 → 落库。

写死原则（第1条）：评分、奖励、等级、技能状态全部规则计算，无大模型参与。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment_review import ExamQuestion
from app.models.business_loop import (
    BOSS_FAILED,
    BOSS_FAIL_BASE_XP,
    BOSS_PASSED,
    BOSS_PASS_BASE_XP,
    BOSS_STARTED,
    BossChallenge,
)
from app.models.learning import (
    ACTION_FINISH,
    MODULE_BOSS,
    LearningArchive,
    LearningRecord,
)
from app.models.skill import (
    NODE_KNOWLEDGE,
    STATUS_LEARNING,
    STATUS_MASTERED,
    SkillNode,
    UserSkillStatus,
)
from app.models.user import User
from app.services.exam_service import is_answer_correct

_BOSS_MIN_QUESTIONS = 5


def _stage_label(skill: SkillNode) -> str:
    """技能 → 演示用段位标签（按 importance 映射，展示 BOSS 层级）。"""
    iv: int = skill.importance if skill.importance else 60
    if iv >= 90:
        return "王者"
    if iv >= 85:
        return "钻石"
    if iv >= 75:
        return "铂金"
    if iv >= 70:
        return "黄金"
    if iv >= 60:
        return "白银"
    return "青铜"


def build_boss_questions(db: Session, skill: SkillNode) -> List[ExamQuestion]:
    """抽取挑战题：优先该技能下属知识点的题目，不足则全局题库补足。"""
    kp_ids = list(
        db.scalars(
            select(SkillNode.id).where(
                SkillNode.parent_id == skill.id,
                SkillNode.node_type == NODE_KNOWLEDGE,
            )
        ).all()
    ) or ([skill.id] if skill.node_type == NODE_KNOWLEDGE else [])

    picked: List[ExamQuestion] = []
    if kp_ids:
        picked = list(
            db.scalars(
                select(ExamQuestion)
                .where(ExamQuestion.knowledge_point_id.in_(kp_ids))
                .order_by(ExamQuestion.id.asc())
            ).all()
        )
    if len(picked) < _BOSS_MIN_QUESTIONS:
        exist_ids = {q.id for q in picked}
        fill = list(
            db.scalars(
                select(ExamQuestion)
                .order_by(ExamQuestion.id.asc())
                .limit(_BOSS_MIN_QUESTIONS * 2)
            ).all()
        )
        picked.extend([q for q in fill if q.id not in exist_ids])
    return picked[:_BOSS_MIN_QUESTIONS]


def start_boss_challenge(db: Session, skill: SkillNode, user_id: int) -> Dict[str, Any]:
    """出题挑战卷（不下发答案），并落一条待完成挑战记录返回 challenge_id。"""
    questions = build_boss_questions(db, skill)
    challenge = BossChallenge(
        user_id=user_id,
        skill_node_id=skill.id,
        skill_name=skill.name,
        score=0,
        status=BOSS_STARTED,
        reward_xp=0,
        result={"question_count": len(questions)},
    )
    db.add(challenge)
    db.flush()
    data = {
        "challenge_id": challenge.id,
        "skill_node_id": skill.id,
        "skill_name": skill.name,
        "stage": _stage_label(skill),
        "description": "Boss 挑战：衡量「{}」的综合掌握度，通过(≥60 分)后升级技能等级并发放经验奖励。".format(
            skill.name
        ),
        "total_points": sum(q.score for q in questions),
        "questions": [
            {
                "id": q.id,
                "question_type": q.question_type,
                "content": q.content,
                "options": q.options_json or [],
                "score": q.score,
                "knowledge_point_id": q.knowledge_point_id,
            }
            for q in questions
        ],
    }
    return data


def finish_boss_challenge(
    db: Session,
    user: User,
    skill: SkillNode,
    answers: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """评分 → XP/等级/技能状态更新 → 落库（BossChallenge + LearningRecord）。"""
    from sqlalchemy import delete

    # 清理该用户尚未提交的 started 会话行，避免悬挂
    db.execute(
        delete(BossChallenge).where(
            BossChallenge.user_id == user.id,
            BossChallenge.skill_node_id == skill.id,
            BossChallenge.status == BOSS_STARTED,
        )
    )

    questions = build_boss_questions(db, skill)
    if not questions:
        raise ValueError("暂无可挑战的题目，请先完成相关阶段测评")

    q_map = {q.id: q for q in questions}
    ans_map = {a["question_id"]: a.get("user_answer") for a in answers}

    earned = 0
    total = 0
    correct = 0
    detail: List[Dict[str, Any]] = []
    for q in questions:
        total += q.score
        ua = ans_map.get(q.id)
        ok = is_answer_correct(q.question_type, q.answer, ua)
        earned += q.score if ok else 0
        if ok:
            correct += 1
        detail.append(
            {
                "question_id": q.id,
                "content": q.content,
                "is_correct": ok,
                "points_earned": q.score if ok else 0,
                "points_total": q.score,
            }
        )

    score = round(earned * 100 / total) if total else 0
    passed = score >= 60

    # ---- XP 奖励（规则）：通过=基础+重要度加成；失败=参与奖 ----
    importance = int(skill.importance or 60)
    reward_xp = BOSS_PASS_BASE_XP + round(importance / 3) if passed else BOSS_FAIL_BASE_XP

    # ---- 学习档案：total_xp / current_level 写库升级 ----
    archive = db.scalar(
        select(LearningArchive)
        .where(LearningArchive.user_id == user.id)
        .order_by(LearningArchive.id.desc())
    )
    if archive is None:
        archive = LearningArchive(
            user_id=user.id, archive_name="我的成长档案", current_level=1, total_xp=0
        )
        db.add(archive)
    archive.total_xp = (archive.total_xp or 0) + reward_xp
    from app.api.v1.endpoints.users import level_from_xp, xp_to_next_level

    new_level = level_from_xp(archive.total_xp)

    # ---- 技能等级/状态更新（Boss 通过 → 达标技能掌握） ----
    status_row = db.scalar(
        select(UserSkillStatus).where(
            UserSkillStatus.user_id == user.id,
            UserSkillStatus.skill_node_id == skill.id,
        )
    )
    if status_row is None:
        status_row = UserSkillStatus(user_id=user.id, skill_node_id=skill.id)
        db.add(status_row)
    if passed:
        new_mastery = max(status_row.mastery_score or 0, score)
    else:
        new_mastery = status_row.mastery_score or 0
    status_row.mastery_score = new_mastery
    status_row.status = (
        STATUS_MASTERED
        if new_mastery >= 80
        else (STATUS_LEARNING if new_mastery > 0 else "not_started")
    )
    db.flush()

    challenge = BossChallenge(
        user_id=user.id,
        skill_node_id=skill.id,
        skill_name=skill.name,
        score=score,
        status=BOSS_PASSED if passed else BOSS_FAILED,
        reward_xp=reward_xp,
        result={
            "correct_count": correct,
            "total_count": len(questions),
            "importance": importance,
            "questions": detail,
        },
    )
    db.add(challenge)
    db.flush()

    # ---- 学习轨迹流水（module=boss） ----
    db.add(
        LearningRecord(
            user_id=user.id,
            module_type=MODULE_BOSS,
            action_type=ACTION_FINISH,
            target_id=skill.id,
            duration=0,
            result={
                "challenge_id": challenge.id,
                "score": score,
                "passed": passed,
                "reward_xp": reward_xp,
                "total_xp": archive.total_xp,
            },
        )
    )
    # ---- XP 流水（游戏化模块；奖励已计入 archive.total_xp，此处仅落流水行） ----
    from app.models.gamification import XP_ACTION_BOSS, XpLog

    db.add(
        XpLog(
            user_id=user.id,
            action_type=XP_ACTION_BOSS,
            xp_amount=reward_xp,
            note=("Boss 挑战通过·「{}」".format(skill.name) if passed
                  else "Boss 挑战参与奖·「{}」".format(skill.name)),
            metadata_json={"challenge_id": challenge.id, "score": score, "passed": passed},
        )
    )
    db.commit()

    return {
        "challenge_id": challenge.id,
        "skill_node_id": skill.id,
        "skill_name": skill.name,
        "score": score,
        "pass_flag": passed,
        "reward_xp": reward_xp,
        "archive_xp": archive.total_xp,
        "level": new_level,
        "xp_to_next_level": xp_to_next_level(archive.total_xp, new_level),
        "skill_mastery": status_row.mastery_score,
        "skill_status": status_row.status,
        "message": (
            "Boss 挑战通过！技能等级已提升，获得 {} XP，当前等级 Lv.{}。".format(
                reward_xp, new_level
            )
            if passed
            else "Boss 挑战未通过(≥60 分通过)，获得参与奖励 {} XP，可复习后再战。".format(
                reward_xp
            )
        ),
    }