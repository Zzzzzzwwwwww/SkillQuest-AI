"""
SkillQuest AI 用户中心接口（模块2）

  - GET  /api/users/me                 当前用户信息（含画像）
  - PUT  /api/users/profile            更新个人信息
  - GET  /api/users/learning-archive   学习档案 + 学习统计
  - GET  /api/users/learning-records   历史学习记录（分页 + 筛选）
  - GET  /api/users/assessment-reports 测评报告列表（分页 + 筛选）

原则（第1条）：总分、等级、XP、统计等一律规则计算，不经过大模型。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.response import success
from app.core.security import get_current_user
from app.db.session import get_db
from app.models import AssessmentReport, LearningArchive, LearningRecord, UserProfile
from app.models.skill import SkillNode, UserSkillStatus
from app.models.user import User
from app.schemas.common import ApiResponse, PageParams, PageResult
from app.schemas.skill import UserSkillStatusItem, UserSkillStatusOut, UserSkillStatusSync
from app.schemas.user import (
    ArchiveOverviewOut,
    AssessmentReportOut,
    ProfileOut,
    ProfileUpdate,
    LearningRecordOut,
    UserWithProfileOut,
)
from app.services.skill_tree import normalize_status

router = APIRouter(prefix="/users", tags=["users"])


# -------------------------------------------------------------------- #
# 等级规则引擎（规则计算，无 AI 参与；后续游戏化模块复用）
# -------------------------------------------------------------------- #
def cumulative_xp_for_level(level: int) -> int:
    """到达 level 级所需的累计 XP = 100 * (1 + 2 + ... + (level-1))。"""
    return 50 * level * (level - 1)


def level_from_xp(total_xp: int) -> int:
    """由累计 XP 反推等级（规则计算）。"""
    level = 1
    while cumulative_xp_for_level(level + 1) <= total_xp:
        level += 1
    return level


def xp_to_next_level(total_xp: int, level: int) -> int:
    """当前等级升到下一级所需 XP（规则计算）。"""
    need_next = cumulative_xp_for_level(level + 1)
    return max(0, need_next - total_xp)


# -------------------------------------------------------------------- #
# 用户信息
# -------------------------------------------------------------------- #
@router.get("/me", response_model=ApiResponse[UserWithProfileOut], summary="获取当前用户信息")
def get_me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """当前用户信息 + 画像（画像未初始化时返回 null）。"""
    profile = db.scalar(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    return success(UserWithProfileOut(
        id=user.id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        avatar=user.avatar,
        status=user.status,
        created_at=user.created_at,
        updated_at=user.updated_at,
        profile=ProfileOut.model_validate(profile) if profile else None,
    ))


@router.put("/profile", response_model=ApiResponse[ProfileOut], summary="更新个人信息")
def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """更新用户画像（部分字段更新），并同步 users.phone / users.avatar。"""
    # 同步 users 表的冗余展示字段
    changed_user = False
    if payload.phone is not None and payload.phone != user.phone:
        user.phone = payload.phone
        changed_user = True
    if payload.avatar is not None and payload.avatar != user.avatar:
        user.avatar = payload.avatar
        changed_user = True

    profile = db.scalar(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)

    update_map: dict = payload.model_dump(exclude_unset=True)
    # phone/avatar 已在 users 表同步，避免覆盖到 profile 的冗余列
    update_map.pop("phone", None)
    update_map.pop("avatar", None)
    for field, value in update_map.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    if changed_user:
        db.refresh(user)
    return success(ProfileOut.model_validate(profile))


# -------------------------------------------------------------------- #
# 学习档案
# -------------------------------------------------------------------- #
@router.get(
    "/learning-archive",
    response_model=ApiResponse[ArchiveOverviewOut],
    summary="学习档案概览",
)
def get_learning_archive(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """最新学习档案 + 规则计算的统计概览。"""
    archive = db.scalar(
        select(LearningArchive)
        .where(LearningArchive.user_id == user.id)
        .order_by(LearningArchive.id.desc())
    )
    if archive is None:
        raise HTTPException(status_code=404, detail="学习档案尚未初始化")

    # ---- 规则统计 ----
    total_records, total_duration, finished_count = db.execute(
        select(
            func.count(LearningRecord.id),
            func.coalesce(func.sum(LearningRecord.duration), 0),
            func.count(LearningRecord.id).filter(
                LearningRecord.action_type == "finish"
            ),
        ).where(LearningRecord.user_id == user.id)
    ).one()

    # ---- 等级规则：按 XP 反推有效等级（GET 不产生写库副作用） ----
    effective_level = level_from_xp(archive.total_xp)
    overview = ArchiveOverviewOut(
        id=archive.id,
        user_id=archive.user_id,
        archive_name=archive.archive_name,
        target_job=archive.target_job,
        current_level=max(archive.current_level, effective_level),
        total_xp=archive.total_xp,
        created_at=archive.created_at,
        updated_at=archive.updated_at,
        total_records=int(total_records),
        total_duration=int(total_duration),
        finished_count=int(finished_count),
        xp_to_next_level=xp_to_next_level(archive.total_xp, effective_level),
    )
    return success(overview)


# -------------------------------------------------------------------- #
# 历史学习记录（分页 + 筛选）
# -------------------------------------------------------------------- #
@router.get(
    "/learning-records",
    response_model=ApiResponse[PageResult[LearningRecordOut]],
    summary="历史学习记录",
)
def get_learning_records(
    module_type: Optional[str] = Query(None, description="模块类型筛选"),
    action_type: Optional[str] = Query(None, description="动作类型筛选"),
    page: PageParams = Depends(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """分页查询学习轨迹，支持模块/动作筛选。"""
    base = select(LearningRecord).where(LearningRecord.user_id == user.id)
    if module_type:
        base = base.where(LearningRecord.module_type == module_type)
    if action_type:
        base = base.where(LearningRecord.action_type == action_type)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = db.scalars(
        base.order_by(LearningRecord.created_at.desc(), LearningRecord.id.desc())
        .offset(page.skip)
        .limit(page.page_size)
    ).all()

    return success(PageResult[LearningRecordOut](
        items=[LearningRecordOut.model_validate(r) for r in items],
        total=total,
        page=page.page,
        page_size=page.page_size,
    ))


# -------------------------------------------------------------------- #
# 测评报告（分页 + 筛选）
# -------------------------------------------------------------------- #
@router.get(
    "/assessment-reports",
    response_model=ApiResponse[PageResult[AssessmentReportOut]],
    summary="测评报告列表",
)
def get_assessment_reports(
    report_type: Optional[str] = Query(None, description="报告类型筛选"),
    page: PageParams = Depends(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """分页查询历史测评报告。"""
    base = select(AssessmentReport).where(AssessmentReport.user_id == user.id)
    if report_type:
        base = base.where(AssessmentReport.report_type == report_type)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = db.scalars(
        base.order_by(AssessmentReport.created_at.desc(), AssessmentReport.id.desc())
        .offset(page.skip)
        .limit(page.page_size)
    ).all()

    return success(PageResult[AssessmentReportOut](
        items=[AssessmentReportOut.model_validate(r) for r in items],
        total=total,
        page=page.page,
        page_size=page.page_size,
    ))


# -------------------------------------------------------------------- #
# 技能掌握状态（模块4）
# -------------------------------------------------------------------- #
@router.get(
    "/{user_id}/skill-status",
    response_model=ApiResponse[UserSkillStatusOut],
    summary="获取用户技能掌握状态",
    description="仅可查看本人的技能掌握状态；他人返回 403。",
)
def get_user_skill_status(
    user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """当前技能掌握状态列表（全部返回）。"""
    if user_id != user.id:
        raise HTTPException(status_code=403, detail="仅可查看本人的技能状态")

    rows = db.scalars(
        select(UserSkillStatus)
        .where(UserSkillStatus.user_id == user.id)
        .order_by(UserSkillStatus.updated_at.desc(), UserSkillStatus.id.desc())
    ).all()
    items = [
        UserSkillStatusItem(
            skill_node_id=r.skill_node_id,
            status=r.status,
            mastery_score=r.mastery_score,
            updated_at=r.updated_at.isoformat() if r.updated_at else None,
        )
        for r in rows
    ]
    return success(UserSkillStatusOut(total=len(items), items=items))


@router.put(
    "/skill-status",
    response_model=ApiResponse[UserSkillStatusOut],
    summary="更新用户技能掌握状态",
    description="批量 upsert：节点存在性校验，状态与掌握度对齐（缺失状态按掌握度规则推导）。",
)
def update_user_skill_status(
    payload: UserSkillStatusSync,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """批量同步技能节点掌握状态（幂等 upsert）。"""
    node_ids = [i.skill_node_id for i in payload.items]
    exist_ids = set(
        db.scalars(select(SkillNode.id).where(SkillNode.id.in_(node_ids))).all()
    )
    missing = [i for i in node_ids if i not in exist_ids]
    if missing:
        raise HTTPException(status_code=400, detail=f"技能节点不存在: {missing[:5]}")

    existing = {
        r.skill_node_id: r
        for r in db.scalars(
            select(UserSkillStatus).where(
                UserSkillStatus.user_id == user.id,
                UserSkillStatus.skill_node_id.in_(node_ids),
            )
        ).all()
    }

    for item in payload.items:
        mastery = max(0, min(100, int(item.mastery_score or 0)))
        row = existing.get(item.skill_node_id)
        if row is None:
            row = UserSkillStatus(
                user_id=user.id,
                skill_node_id=item.skill_node_id,
                mastery_score=mastery,
            )
            db.add(row)
        else:
            row.mastery_score = mastery
        row.status = normalize_status(item.status, mastery)
    db.commit()

    # 返回同步后全量状态
    rows = db.scalars(
        select(UserSkillStatus)
        .where(UserSkillStatus.user_id == user.id)
        .order_by(UserSkillStatus.updated_at.desc(), UserSkillStatus.id.desc())
    ).all()
    items = [
        UserSkillStatusItem(
            skill_node_id=r.skill_node_id,
            status=r.status,
            mastery_score=r.mastery_score,
            updated_at=r.updated_at.isoformat() if r.updated_at else None,
        )
        for r in rows
    ]
    return success(UserSkillStatusOut(total=len(items), items=items))