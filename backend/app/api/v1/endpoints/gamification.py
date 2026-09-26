"""
SkillQuest AI 游戏化接口（模块9：成长激励体系）

  - GET  /gamification/overview          成长首页聚合（等级/段位/XP/连击/今日任务/成就/番茄钟）
  - GET  /gamification/achievements      成就中心（已解锁/未解锁）
  - GET  /gamification/xp-logs           XP 流水（分页）
  - POST /gamification/checkin           每日打卡（+10 XP，当天一次）
  - POST /gamification/pomodoro          番茄钟完成（25/40 分钟模式，+XP）
  - GET  /gamification/today-tasks       每日督导（规则任务 + Coach Agent 增强）
  - POST /gamification/tasks/complete    完成每日任务（规则奖励 XP）
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.response import success
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.gamification import XpLog
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.gamification import (
    AchievementCenterOut,
    CheckinOut,
    DailySupervisionOut,
    DailyTaskCompleteOut,
    GamificationOverviewOut,
    PomodoroIn,
    PomodoroOut,
)
from app.services import gamification as game

router = APIRouter(prefix="/gamification", tags=["gamification"])


@router.get(
    "/overview",
    response_model=ApiResponse[GamificationOverviewOut],
    summary="成长首页聚合",
    description="等级/段位/XP/连击/今日任务/成就/番茄钟一次取回（全部规则计算）。",
)
def overview(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    data = game.build_overview(db, user.id)
    try:
        db.commit()
    finally:
        pass
    return success(data)


@router.get(
    "/achievements",
    response_model=ApiResponse[AchievementCenterOut],
    summary="成就中心",
    description="全部成就 + 已解锁状态（隐藏成就未解锁时不展示条件）。",
)
def achievements(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    freshly = game.try_unlock_achievements(db, user.id)
    if freshly:
        db.commit()
    return success(game.user_achievements_view(db, user.id))


@router.get(
    "/xp-logs",
    summary="XP 流水",
    description="分页返回 XP 获得记录（倒序）。",
)
def xp_logs(
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    total = db.scalar(
        select(func.count(XpLog.id)).where(XpLog.user_id == user.id)
    )
    rows = db.scalars(
        select(XpLog)
        .where(XpLog.user_id == user.id)
        .order_by(XpLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": r.id,
            "action_type": r.action_type,
            "xp_amount": r.xp_amount,
            "note": r.note,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]
    return success(
        {
            "items": items,
            "total": int(total or 0),
            "page": page,
            "page_size": page_size,
        }
    )


@router.post(
    "/checkin",
    response_model=ApiResponse[CheckinOut],
    summary="每日打卡",
    description="当天首次打卡 +10 XP（重复打卡返回已打卡状态）。",
)
def checkin(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = game.check_in(db, user.id)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    db.commit()
    return success(result)


@router.post(
    "/pomodoro",
    response_model=ApiResponse[PomodoroOut],
    summary="完成番茄钟",
    description="focus: 专注25min/休息5min +8XP；deep: 专注40min/休息10min +12XP。",
)
def pomodoro(
    payload: PomodoroIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if payload.mode not in ("focus", "deep"):
        raise HTTPException(status_code=422, detail="mode 必须为 focus 或 deep")
    result = game.complete_pomodoro(db, user.id, payload.mode, payload.note or "")
    db.commit()
    return success(result)


@router.get(
    "/today-tasks",
    response_model=ApiResponse[DailySupervisionOut],
    summary="每日督导",
    description="规则生成今日任务，Coach Agent 生成计划与激励语（未配置自动降级）。",
)
async def today_tasks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    data = await game.build_daily_supervision(db, user.id)
    return success(data)


@router.post(
    "/tasks/complete",
    response_model=ApiResponse[DailyTaskCompleteOut],
    summary="完成每日任务",
    description="按规则发放任务 XP；同一天同一任务只发一次。",
)
def complete_task(
    payload: Dict[str, Any],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    task_id = str((payload or {}).get("task_id", "")).strip()
    if not task_id:
        raise HTTPException(status_code=422, detail="task_id 不能为空")
    try:
        result = game.complete_daily_task(db, user.id, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return success(result)