"""
SkillQuest AI Boss 挑战接口（模块8 业务闭环6）

  - POST /boss/start    开始 Boss 挑战（按技能抽取题目，不下发答案）
  - POST /boss/finish   完成挑战：规则评分 → XP/等级/技能等级自动更新

流程：用户从技能图谱选择一个技能发起挑战 → 答题提交 →
      通过(≥60 分)升级技能等级并发放 XP，失败仅发放参与奖励。
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.response import success
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.skill import SkillNode
from app.models.user import User
from app.schemas.boss import (
    BossFinishIn,
    BossFinishOut,
    BossStartIn,
    BossStartOut,
)
from app.schemas.common import ApiResponse
from app.services.boss_service import finish_boss_challenge, start_boss_challenge

router = APIRouter(prefix="/boss", tags=["boss"])


def _get_skill_or_404(db: Session, skill_node_id: int) -> SkillNode:
    skill = db.get(SkillNode, skill_node_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="技能节点不存在")
    return skill


@router.post(
    "/start",
    response_model=ApiResponse[BossStartOut],
    summary="开始 Boss 挑战",
    description="按所选技能抽取挑战题目（复用阶段测评题库，不下发答案）。",
)
def boss_start(
    payload: BossStartIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    skill = _get_skill_or_404(db, payload.skill_node_id)
    data = start_boss_challenge(db, skill, user.id)
    db.commit()
    return success(data)


@router.post(
    "/finish",
    response_model=ApiResponse[BossFinishOut],
    summary="完成 Boss 挑战",
    description="规则评分并自动发放 XP、升级技能等级（写入学习档案与技能图谱）。",
)
def boss_finish(
    payload: BossFinishIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    skill = _get_skill_or_404(db, payload.skill_node_id)
    try:
        result = finish_boss_challenge(
            db, user, skill, [a.model_dump() for a in payload.answers]
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    return success(result)