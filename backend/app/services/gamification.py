"""
SkillQuest AI 游戏化服务（模块9：成长激励体系）

规则引擎（全部无大模型参与）：
  - XP：完成学习/任务/项目/番茄钟/答疑/Boss/弱点攻克 → 规则定额发放，写 xp_logs + 累加档案
  - 等级：沿用数值等级规则（users.level_from_xp），并映射为六段位（青铜→王者）
  - 连击：连续学习天数（有学习行为即计一天，从今天/昨天起往前连续计）
  - 成就：条件由 achievements.condition_json 描述，服务统一校验并幂等解锁
  - 每日督导：规则生成今日任务（弱点/路径当前节点/练习），Coach Agent 可选增强，未配置降级

第1条原则：能规则算的不用大模型 —— 段位/连击/成就/XP 全部规则计算。
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.gamification import (
    Achievement,
    POMODORO_DEEP,
    POMODORO_FOCUS,
    PomodoroSession,
    UserAchievement,
    XP_ACTION_ACHIEVEMENT,
    XP_ACTION_BOSS,
    XP_ACTION_POMODORO,
    XP_ACTION_PROJECT,
    XP_ACTION_QUESTION,
    XP_ACTION_STUDY,
    XP_ACTION_TASK,
    XP_ACTION_WEAKNESS,
    XpLog,
)

# --------------------------------------------------------------------- #
# XP 规则（规则表：谁给多少 XP，可随产品策略调整）
# --------------------------------------------------------------------- #
ACTION_XP_RULES: Dict[str, int] = {
    XP_ACTION_STUDY: 20,           # 完成一项学习资源/课程
    XP_ACTION_TASK: 15,            # 完成一个每日任务
    XP_ACTION_PROJECT: 50,         # 完成一个项目
    XP_ACTION_BOSS: 0,             # Boss 奖励由 boss_service 处理，此处仅记录
    XP_ACTION_QUESTION: 5,         # 一次 AI 导师答疑
    XP_ACTION_POMODORO: 10,        # 完成一整个番茄钟
    XP_ACTION_WEAKNESS: 20,        # 攻克一个弱点诊断
    XP_ACTION_ACHIEVEMENT: 0,      # 成就奖励取 achievements.xp_reward
}

# 六段位规则：level 下限 -> (key, 显示名)
TIER_RULES: List[tuple] = [
    (14, "king", "王者"),
    (10, "diamond", "钻石"),
    (7, "platinum", "铂金"),
    (5, "gold", "黄金"),
    (3, "silver", "白银"),
    (0, "bronze", "青铜"),
]
TIER_LABELS = {k: label for _, k, label in TIER_RULES}
TIER_KEYS = list(reversed([k for _, k, _ in TIER_RULES]))  # 低→高：青铜..王者

# 番茄钟模式配置
POMODORO_MODES = {
    POMODORO_FOCUS: {"focus": 25, "break": 5, "xp": 8},
    POMODORO_DEEP: {"focus": 40, "break": 10, "xp": 12},
}


# --------------------------------------------------------------------- #
# 等级/段位（规则计算）
# --------------------------------------------------------------------- #
def tier_of(level: int) -> str:
    """数值等级 -> 段位 key（青铜→王者）。"""
    for min_level, key, _ in TIER_RULES:
        if level >= min_level:
            return key
    return "bronze"


def tier_index_of(level: int) -> int:
    """段位在整个递增序列中的下标（0=青铜...5=王者）。"""
    key = tier_of(level)
    try:
        return TIER_KEYS.index(key)
    except ValueError:
        return 0


def tier_percentage(level: int, total_xp: int) -> float:
    """当前段位内升级进度 0-100（规则：段内按有效等级均匀推进）。"""
    if level <= 1:
        return 0.0
    idx = tier_index_of(level)
    # 段位内按等级细分：每 1 级推进 20%
    sub = (level % 5) or 5
    return min(100.0, round(((sub - 1) * 20) + 2, 1))


# --------------------------------------------------------------------- #
# XP 发放（写流水 + 累加档案）
# --------------------------------------------------------------------- #
def add_xp(
    db: Session,
    user_id: int,
    action_type: str,
    amount: int,
    note: str = "",
    metadata: Optional[dict] = None,
) -> XpLog:
    """发放 XP：写 xp_logs + 累加 learning_archives.total_xp。返回流水行。"""
    from app.models.learning import LearningArchive

    log = XpLog(
        user_id=user_id,
        action_type=action_type,
        xp_amount=amount,
        note=note or "",
        metadata_json=metadata,
    )
    db.add(log)
    archive = db.scalar(
        select(LearningArchive)
        .where(LearningArchive.user_id == user_id)
        .order_by(LearningArchive.id.desc())
    )
    if archive is None:
        archive = LearningArchive(
            user_id=user_id, archive_name="我的成长档案", current_level=1, total_xp=0
        )
        db.add(archive)
    archive.total_xp = (archive.total_xp or 0) + amount
    return log


def record_action_xp(
    db: Session,
    user_id: int,
    action_type: str,
    note: str = "",
    metadata: Optional[dict] = None,
    amount: Optional[int] = None,
) -> Dict[str, Any]:
    """按规则表发放一枚 XP（amount 缺省用 ACTION_XP_RULES）。返回发放详情。"""
    xp = amount if amount is not None else ACTION_XP_RULES.get(action_type, 0)
    log = add_xp(db, user_id, action_type, xp, note, metadata)
    return {
        "action_type": action_type,
        "xp_amount": xp,
        "note": note,
        "log_id": log.id,
    }


def today_xp(db: Session, user_id: int) -> int:
    """今日累计 XP（规则计算）。"""
    today0 = datetime.combine(date.today(), datetime.min.time())
    t = db.scalar(
        select(func.coalesce(func.sum(XpLog.xp_amount), 0)).where(
            XpLog.user_id == user_id, XpLog.created_at >= today0
        )
    )
    return int(t or 0)


def recent_xp_logs(db: Session, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """最近 XP 流水（倒序）。"""
    rows = db.scalars(
        select(XpLog)
        .where(XpLog.user_id == user_id)
        .order_by(XpLog.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "action_type": r.action_type,
            "xp_amount": r.xp_amount,
            "note": r.note,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


# --------------------------------------------------------------------- #
# 连击：连续学习天数（规则计算）
# --------------------------------------------------------------------- #
def _study_dates(db: Session, user_id: int) -> List[date]:
    """有学习行为的日期集合（XpLog 或 LearningRecord）。"""
    from app.models.learning import LearningRecord

    dates: set = set()

    def _fmt(dt: datetime) -> date:
        return dt.date()

    for d in db.scalars(
        select(func.date(XpLog.created_at)).where(XpLog.user_id == user_id)
    ).all():
        try:
            dates.add(date.fromisoformat(str(d)))
        except ValueError:
            pass
    for d in db.scalars(
        select(func.date(LearningRecord.created_at)).where(
            LearningRecord.user_id == user_id
        )
    ).all():
        try:
            dates.add(date.fromisoformat(str(d)))
        except ValueError:
            pass
    return sorted(dates)


def compute_streak(db: Session, user_id: int) -> int:
    """连续学习天数：以今天或昨天为终点，往前数连续有学习行为的天数。"""
    dates = _study_dates(db, user_id)
    if not dates:
        return 0
    today = date.today()
    last = dates[-1]
    if (today - last).days > 1:
        return 0  # 已中断
    streak = 1
    cursor = last - timedelta(days=1)
    stayed = set(dates)
    while cursor in stayed:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def check_in(db: Session, user_id: int) -> Dict[str, Any]:
    """每日打卡：当天首次打卡 +10 XP，重复打卡返回已打卡。"""
    today0 = datetime.combine(date.today(), datetime.min.time())
    exist = db.scalar(
        select(XpLog.id).where(
            XpLog.user_id == user_id,
            XpLog.action_type == "checkin",
            XpLog.created_at >= today0,
        )
    )
    if exist is not None:
        return {
            "already_checked": True,
            "xp_amount": 0,
            "streak": compute_streak(db, user_id),
            "message": "今天已经打过卡啦，保持节奏！",
        }
    add_xp(db, user_id, "checkin", 10, "每日打卡")
    db.flush()
    return {
        "already_checked": False,
        "xp_amount": 10,
        "streak": compute_streak(db, user_id),
        "message": "打卡成功 +10 XP",
    }


# --------------------------------------------------------------------- #
# 成就解锁（规则引擎：读取 condition_json）
# --------------------------------------------------------------------- #
def _achievement_met(
    db: Session, user_id: int, cond: Dict[str, Any]
) -> bool:
    """判断单个成就条件是否满足（规则引擎）。"""
    ctype = cond.get("type", "")
    mini = int(cond.get("min", 1))
    from app.models.learning import LearningArchive

    if ctype == "total_xp":
        xp = db.scalar(
            select(LearningArchive.total_xp).where(
                LearningArchive.user_id == user_id
            )
        )
        return int(xp or 0) >= mini
    if ctype == "streak":
        return compute_streak(db, user_id) >= mini
    if ctype == "qa_count":
        from app.models.chat import QaLog

        n = db.scalar(
            select(func.count(QaLog.id)).where(QaLog.user_id == user_id)
        )
        return int(n or 0) >= mini
    if ctype == "boss_pass":
        from app.models.business_loop import BOSS_PASSED, BossChallenge

        n = db.scalar(
            select(func.count(BossChallenge.id)).where(
                BossChallenge.user_id == user_id,
                BossChallenge.status == BOSS_PASSED,
            )
        )
        return int(n or 0) >= mini
    if ctype == "mastered_skills":
        from app.models.skill import STATUS_MASTERED, UserSkillStatus

        n = db.scalar(
            select(func.count(UserSkillStatus.id)).where(
                UserSkillStatus.user_id == user_id,
                UserSkillStatus.status == STATUS_MASTERED,
            )
        )
        return int(n or 0) >= mini
    return False


def try_unlock_achievements(
    db: Session, user_id: int
) -> List[Dict[str, Any]]:
    """扫描全部成就，满足条件且未解锁的自动解锁（幂等），并发放成就 XP。"""
    unlocked: List[Dict[str, Any]] = []
    achievements = db.scalars(
        select(Achievement).order_by(Achievement.sort_order.asc())
    ).all()
    for a in achievements:
        exists = db.scalar(
            select(UserAchievement.id).where(
                UserAchievement.user_id == user_id,
                UserAchievement.achievement_id == a.id,
            )
        )
        if exists is not None:
            continue
        cond = a.condition_json or {}
        if not _achievement_met(db, user_id, cond):
            continue
        db.add(
            UserAchievement(user_id=user_id, achievement_id=a.id)
        )
        if a.xp_reward:
            add_xp(
                db, user_id, XP_ACTION_ACHIEVEMENT, a.xp_reward,
                f"成就解锁「{a.title}」", {"achievement_id": a.id},
            )
        unlocked.append(
            {
                "achievement_id": a.id,
                "name": a.name,
                "title": a.title,
                "xp_reward": a.xp_reward,
            }
        )
    if unlocked:
        db.flush()
    return unlocked


def user_achievements_view(
    db: Session, user_id: int
) -> Dict[str, Any]:
    """成就中心视图：全部成就 + 已解锁状态 + 统计。"""
    achievements = db.scalars(
        select(Achievement).order_by(Achievement.sort_order.asc())
    ).all()
    unlocked_map = {
        a.achievement_id: a.unlocked_at
        for a in db.scalars(
            select(UserAchievement).where(UserAchievement.user_id == user_id)
        ).all()
    }
    unlocked_count = 0
    items = []
    for a in achievements:
        unlocked = a.id in unlocked_map
        if unlocked:
            unlocked_count += 1
        items.append(
            {
                "achievement_id": a.id,
                "name": a.name,
                "title": a.title,
                "description": a.description if not a.hidden or unlocked else "……",
                "icon": a.icon,
                "hidden": bool(a.hidden),
                "unlocked": unlocked,
                "unlocked_at": (
                    unlocked_map[a.id].isoformat() if unlocked else None
                ),
                "xp_reward": a.xp_reward,
            }
        )
    return {
        "total": len(achievements),
        "unlocked_count": unlocked_count,
        "items": items,
    }


# --------------------------------------------------------------------- #
# 番茄钟
# --------------------------------------------------------------------- #
def complete_pomodoro(
    db: Session, user_id: int, mode: str, note: str = ""
) -> Dict[str, Any]:
    """完成一回番茄钟专注（focus 25min / deep 40min），落库并发 XP。"""
    cfg = POMODORO_MODES.get(mode, POMODORO_MODES[POMODORO_FOCUS])
    session = PomodoroSession(
        user_id=user_id,
        mode=mode,
        focus_minutes=cfg["focus"],
        break_minutes=cfg["break"],
        rounds=1,
        note=note or "",
        xp_earned=cfg["xp"],
    )
    db.add(session)
    add_xp(db, user_id, XP_ACTION_POMODORO, cfg["xp"], "完成一回番茄钟专注")
    db.flush()
    return {
        "session_id": session.id,
        "mode": mode,
        "focus_minutes": cfg["focus"],
        "break_minutes": cfg["break"],
        "xp_amount": cfg["xp"],
        "message": "专注完成！休息一下再战。",
    }


def pomodoro_stats(db: Session, user_id: int) -> Dict[str, Any]:
    """番茄钟统计（规则计算）。"""
    total_min = db.scalar(
        select(func.coalesce(func.sum(PomodoroSession.focus_minutes), 0)).where(
            PomodoroSession.user_id == user_id
        )
    )
    count = db.scalar(
        select(func.count(PomodoroSession.id)).where(
            PomodoroSession.user_id == user_id
        )
    )
    return {
        "session_count": int(count or 0),
        "focus_total_minutes": int(total_min or 0),
    }


# --------------------------------------------------------------------- #
# 每日督导：规则生成今日任务 + Coach Agent 可选增强
# --------------------------------------------------------------------- #
def _first_unfinished_path_node(db: Session, user_id: int) -> Optional[dict]:
    """取当前进行中学习路径的第一个未完成节点（规则）。"""
    from app.models.learning_path import (
        NODE_COMPLETED,
        PATH_ACTIVE,
        LearningPath,
        LearningPathNode,
    )
    from app.models.skill import SkillNode
    from app.services.learning_path_service import compute_progress_map

    path = db.scalar(
        select(LearningPath)
        .where(LearningPath.user_id == user_id, LearningPath.status == PATH_ACTIVE)
        .order_by(LearningPath.id.desc())
    )
    if path is None:
        return None
    progress = compute_progress_map(db, user_id, path.id)
    nodes = db.scalars(
        select(LearningPathNode)
        .where(LearningPathNode.path_id == path.id)
        .order_by(LearningPathNode.order_no.asc())
    ).all()
    for n in nodes:
        if progress.get(n.id, 0) < 80:
            skill = db.get(SkillNode, n.skill_node_id)
            return {"node_id": n.id, "name": skill.name if skill else "学习任务"}
    return None


def _weakness_todo(db: Session, user_id: int) -> Optional[dict]:
    """取一条待攻克弱点诊断（规则）。"""
    from app.models.business_loop import (
        DIAG_NEW,
        DIAG_NOTIFIED,
        DIAG_TREATED,
        WeaknessDiagnostic,
    )

    d = db.scalar(
        select(WeaknessDiagnostic)
        .where(
            WeaknessDiagnostic.user_id == user_id,
            WeaknessDiagnostic.status.in_([DIAG_NEW, DIAG_NOTIFIED]),
        )
        .order_by(WeaknessDiagnostic.id.asc())
    )
    if d is None or d.status == DIAG_TREATED:
        return None
    return {"diagnosis_id": d.id, "name": d.kp_name, "domain": d.domain}


def build_daily_tasks(db: Session, user_id: int) -> List[Dict[str, Any]]:
    """规则生成今日任务（弱点攻克 / 路径推进 / 番茄钟 / 答疑）。"""
    tasks: List[Dict[str, Any]] = []
    weakness = _weakness_todo(db, user_id)
    if weakness:
        tasks.append(
            {
                "task_id": "weakness",
                "type": "weakness",
                "title": f"攻克弱点「{weakness['name']}」",
                "detail": f"能力域：{weakness['domain']}，建议针对性练习与提问。",
                "xp": ACTION_XP_RULES[XP_ACTION_WEAKNESS],
            }
        )
    node = _first_unfinished_path_node(db, user_id)
    if node:
        tasks.append(
            {
                "task_id": "path_node",
                "type": "study",
                "title": f"学习「{node['name']}」",
                "detail": "推进当前学习路径节点，完成课程或练习。",
                "xp": ACTION_XP_RULES[XP_ACTION_STUDY],
            }
        )
    tasks.append(
        {
            "task_id": "pomodoro",
            "type": "pomodoro",
            "title": "完成一回番茄钟专注（25 分钟）",
            "detail": "开启专注模式，沉浸学习不被干扰。",
            "xp": ACTION_XP_RULES[XP_ACTION_POMODORO],
        }
    )
    tasks.append(
        {
            "task_id": "ask_tutor",
            "type": "question",
            "title": "向 AI 导师提一个问题",
            "detail": "带着疑问去答疑，把卡点问明白。",
            "xp": ACTION_XP_RULES[XP_ACTION_QUESTION],
        }
    )
    return tasks[:4]


async def build_daily_supervision(
    db: Session, user_id: int
) -> Dict[str, Any]:
    """每日督导：规则任务 + Coach Agent 生成计划与激励语（未配置自动降级）。"""
    tasks = build_daily_tasks(db, user_id)
    fallback = {
        "daily_plan": [
            {"task": t["title"], "estimated_minutes": 25 if t["type"] != "pomodoro" else 25}
            for t in tasks
        ],
        "pomodoro_suggestion": {
            "focus_minutes": 25, "break_minutes": 5, "rounds": 4,
            "tip": "把今日任务拆成 2-3 个番茄钟逐一完成。",
        },
        "encouragement": "今天也是升级的一天：先聚焦最重要的一个任务，逐个击破！",
    }
    from app.services.agent_service import AgentInput, agent_service

    result = await agent_service.run(
        AgentInput(
            agent_type="coach",
            user_context={
                "today_tasks": tasks,
                "streak": compute_streak(db, user_id),
            },
            fallback=fallback,
            max_tokens=512,
        )
    )
    data = result.data if (not result.degraded and result.data) else fallback
    plan = data.get("daily_plan") or []
    return {
        "tasks": tasks,
        "coach_plan": plan if isinstance(plan, list) else [],
        "pomodoro_suggestion": data.get("pomodoro_suggestion") or fallback["pomodoro_suggestion"],
        "encouragement": str(data.get("encouragement") or fallback["encouragement"])[:200],
        "degraded": result.degraded or not result.ok,
    }


def complete_daily_task(
    db: Session, user_id: int, task_id: str
) -> Dict[str, Any]:
    """完成一个每日任务：校验任务存在 → 按规则发放 XP（同一天同一任务只发一次）。"""
    tasks = build_daily_tasks(db, user_id)
    task = next((t for t in tasks if t["task_id"] == task_id), None)
    if task is None:
        raise ValueError(f"任务不存在: {task_id}")
    today0 = datetime.combine(date.today(), datetime.min.time())
    dup = db.scalar(
        select(XpLog.id).where(
            XpLog.user_id == user_id,
            XpLog.action_type == "daily_task",
            XpLog.created_at >= today0,
        )
    )
    # 同一类型任务当天去重（note 记录任务名）
    if dup is not None:
        return {
            "task_id": task_id,
            "already_done": True,
            "xp_amount": 0,
            "message": "该任务今天已经完成过啦。",
        }
    add_xp(
        db, user_id, "daily_task", task["xp"],
        f"完成任务「{task['title']}」", {"task_id": task_id},
    )
    db.flush()
    return {
        "task_id": task_id,
        "already_done": False,
        "xp_amount": task["xp"],
        "message": f"任务完成 +{task['xp']} XP",
    }


# --------------------------------------------------------------------- #
# 成长首页聚合
# --------------------------------------------------------------------- #
def build_overview(db: Session, user_id: int) -> Dict[str, Any]:
    """成长首页聚合数据（等级/段位/XP/连击/今日任务/成就/番茄钟）。"""
    from app.models.learning import LearningArchive

    archive = db.scalar(
        select(LearningArchive)
        .where(LearningArchive.user_id == user_id)
        .order_by(LearningArchive.id.desc())
    )
    if archive is None:
        archive = LearningArchive(
            user_id=user_id, archive_name="我的成长档案", current_level=1, total_xp=0
        )
        db.add(archive)
        db.flush()
    from app.api.v1.endpoints.users import level_from_xp, xp_to_next_level

    level = max(archive.current_level or 1, level_from_xp(archive.total_xp))
    total_xp = archive.total_xp or 0
    streaks = compute_streak(db, user_id)
    # 尝试解锁（幂等），可能带动新成就奖励
    freshly = try_unlock_achievements(db, user_id)
    if freshly:
        db.flush()
    achievements = user_achievements_view(db, user_id)
    tasks = build_daily_tasks(db, user_id)
    pomo = pomodoro_stats(db, user_id)
    return {
        "level": level,
        "tier_key": tier_of(level),
        "tier_label": TIER_LABELS[tier_of(level)],
        "tier_index": tier_index_of(level),
        "tier_percent": tier_percentage(level, total_xp),
        "total_xp": total_xp,
        "xp_to_next_level": xp_to_next_level(total_xp, level),
        "today_xp": today_xp(db, user_id),
        "streak": streaks,
        "checked_in_today": _checked_in_today(db, user_id),
        "pomodoro": pomo,
        "daily_tasks": tasks,
        "achievements": achievements,
        "recent_xp_logs": recent_xp_logs(db, user_id, 8),
    }


def _checked_in_today(db: Session, user_id: int) -> bool:
    today0 = datetime.combine(date.today(), datetime.min.time())
    return (
        db.scalar(
            select(XpLog.id).where(
                XpLog.user_id == user_id,
                XpLog.action_type == "checkin",
                XpLog.created_at >= today0,
            )
        )
        is not None
    )