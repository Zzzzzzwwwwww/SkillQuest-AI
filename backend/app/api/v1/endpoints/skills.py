"""
SkillQuest AI 岗位技能图谱接口（模块4）

  - GET /jobs        岗位列表（岗位族/行业/状态筛选）
  - GET /jobs/{id}/skill-tree  岗位分层技能树（含当前用户掌握状态 + Gap 汇总）
  - GET /skills/{id}/detail    技能详情 / 前置知识 / 推荐资源 / 关联岗位

用户技能掌握状态的读写接口置于 users 模块（GET /users/{id}/skill-status、
PUT /users/skill-status），与用户中心保持同一前缀。
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.response import success
from app.core.security import get_current_user
from app.db.session import get_db
from app.models import Job, JobSkillRelation, SkillNode
from app.models.skill import JOB_ACTIVE, JOB_OFFLINE
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.skill import (
    JobOut,
    JobSelectIn,
    JobSelectOut,
    JobSkillTreeOut,
    SkillDetailOut,
    SkillGapSummary,
    SkillNodeOut,
)
from app.services.skill_tree import (
    SkillTreeBuilder,
    build_skill_detail,
    compute_skill_gaps,
)

jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])
skills_router = APIRouter(prefix="/skills", tags=["skills"])


# -------------------------------------------------------------------- #
# 岗位列表
# -------------------------------------------------------------------- #
@jobs_router.get(
    "",
    response_model=ApiResponse[List[JobOut]],
    summary="岗位列表",
    description="按岗位族/行业/状态筛选,返回岗位与关联技能数。",
)
def list_jobs(
    family: Optional[str] = Query(None, description="岗位族"),
    industry: Optional[str] = Query(None, description="行业"),
    status: Optional[str] = Query(None, description="状态 active/offline"),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """岗位列表（默认仅 active）。"""
    base = select(Job)
    if family:
        base = base.where(Job.job_family == family)
    if industry:
        base = base.where(Job.industry == industry)
    if status is None:
        base = base.where(Job.status == JOB_ACTIVE)
    else:
        base = base.where(Job.status == status)

    jobs = db.scalars(base.order_by(Job.job_family.asc(), Job.id.asc())).all()

    counts: dict = {}
    if jobs:
        counts = dict(
            db.execute(
                select(JobSkillRelation.job_id, func.count(JobSkillRelation.id))
                .where(JobSkillRelation.job_id.in_([j.id for j in jobs]))
                .group_by(JobSkillRelation.job_id)
            ).all()
        )

    return success([
        JobOut(
            id=j.id,
            job_name=j.job_name,
            job_family=j.job_family,
            description=j.description,
            industry=j.industry,
            status=j.status,
            skill_count=int(counts.get(j.id, 0)),
        )
        for j in jobs
    ])


# -------------------------------------------------------------------- #
# 选定目标岗位（业务闭环3：自动生成技能图谱 + 学习路径）
# -------------------------------------------------------------------- #
@jobs_router.post(
    "/select",
    response_model=ApiResponse[JobSelectOut],
    summary="选定目标岗位",
    description="用户选定岗位后：自动回写画像 target_job、学习档案目标岗位，并自动生成学习路径。",
)
async def select_job(
    payload: JobSelectIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    job = db.get(Job, payload.job_id)
    if job is None or job.status == JOB_OFFLINE:
        raise HTTPException(status_code=404, detail="岗位不存在或已下线")

    from app.services.business_flow import auto_generate_learning_path, select_target_job

    select_target_job(db, user, job)

    auto_generated = False
    path = None
    meta = None
    if payload.auto_generate_path:
        result = await auto_generate_learning_path(db, user, job)
        path = result["path"]
        meta = result["meta"]
        auto_generated = True
    else:
        db.commit()

    return success(
        JobSelectOut(
            job_id=job.id,
            job_name=job.job_name,
            job_family=job.job_family,
            target_job=job.job_name,
            auto_generated_path=auto_generated,
            path=path,
            meta=meta,
        )
    )


# -------------------------------------------------------------------- #
# 岗位分层技能树
# -------------------------------------------------------------------- #
@jobs_router.get(
    "/{job_id}/skill-tree",
    response_model=ApiResponse[JobSkillTreeOut],
    summary="岗位分层技能树",
    description="返回 岗位→能力域→技能→知识点 树,并叠加当前用户掌握状态与 Gap 汇总。",
)
def get_job_skill_tree(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """岗位技能树 + 用户状态标注 + Skill Gap 汇总。"""
    job = db.get(Job, job_id)
    if job is None or job.status == JOB_OFFLINE:
        raise HTTPException(status_code=404, detail="岗位不存在或已下线")

    tree = SkillTreeBuilder(db, user.id).build(job)
    summary = compute_skill_gaps(db, job, user.id)

    return success(
        JobSkillTreeOut(
            job=JobOut(
                id=job.id,
                job_name=job.job_name,
                job_family=job.job_family,
                description=job.description,
                industry=job.industry,
                status=job.status,
                skill_count=len(tree.get("children", [])),
            ),
            tree=SkillNodeOut.model_validate(tree),
            summary=SkillGapSummary.model_validate(summary).model_dump(),
        )
    )


# -------------------------------------------------------------------- #
# 技能详情
# -------------------------------------------------------------------- #
@skills_router.get(
    "/{node_id}/detail",
    response_model=ApiResponse[SkillDetailOut],
    summary="技能节点详情",
    description="技能详情 / 前置知识(含掌握状态) / 推荐资源 / 关联岗位及要求。",
)
def get_skill_detail(
    node_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """技能节点详情。"""
    node = db.get(SkillNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="技能节点不存在")

    detail = build_skill_detail(db, node, user.id)
    return success(SkillDetailOut.model_validate(detail))