"""
SkillQuest AI 个性化导学接口（模块5）

  - POST /learning-path/generate   根据画像/目标岗位/技能短板生成学习路径
  - GET  /learning-path/current    当前进行中的路径
  - GET  /learning-path/{id}/map   路径分段地图
  - PUT  /learning-progress        更新节点进度（断点续学位置）
  - POST /learning-progress/resume 断点续学（返回上次学习位置）
  - GET  /learning-resources/recommend  资源推荐（规则评分）

原则（第1条）：路径生成/排序/段位/时长/评分全部规则计算，
Learning Agent 仅增强路径名称与段位目标（未配置 LLM 时规则降级）。
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.response import success
from app.core.security import get_current_user
from app.db.session import get_db
from app.models import (
    Job,
    JobSkillRelation,
    SkillNode,
    UserSkillStatus,
)
from app.models.learning_path import (
    NODE_COMPLETED,
    PATH_ACTIVE,
    PATH_COMPLETED,
    LearningPath,
    LearningPathNode,
    LearningProgress,
)
from app.models.persona import UserPersona
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.learning_path import (
    GeneratePathIn,
    GeneratePathOut,
    LearningPathMapOut,
    RecommendIn,
    ResumeIn,
    ResumePathOut,
    UpdateProgressIn,
    UpdateProgressOut,
)
from app.services.llm import llm_service
from app.services.learning_path_service import (
    build_path_map,
    compute_progress_map,
    enhance_with_learning_agent,
    plan_path,
    recommend_resources,
    set_user_status_map,
    should_complete_path,
)

path_router = APIRouter(prefix="/learning-path", tags=["learning-path"])
progress_router = APIRouter(prefix="/learning-progress", tags=["learning-progress"])
resource_router = APIRouter(
    prefix="/learning-resources", tags=["learning-resources"]
)


# -------------------------------------------------------------------- #
# 工具：取岗位 / 画像目标岗位
# -------------------------------------------------------------------- #
def _resolve_target_job(
    db: Session, user: User, job_id: Optional[int], job_name: Optional[str]
) -> Job:
    """确定目标岗位：入参 job_id/job_name > 画像 target_job > 最近测评推荐。"""
    if job_id:
        job = db.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="岗位不存在")
        return job
    if job_name:
        job = db.scalar(select(Job).where(Job.job_name == job_name))
        if job is None:
            raise HTTPException(status_code=404, detail="岗位不存在")
        return job

    persona = db.scalar(select(UserPersona).where(UserPersona.user_id == user.id))
    if persona and persona.target_job:
        job = db.scalar(select(Job).where(Job.job_name == persona.target_job))
        if job is not None:
            return job
    # 兜底：最近一次测评推荐 Top1 岗位
    from app.models.assessment import AssessmentResult

    result = db.scalar(
        select(AssessmentResult)
        .where(AssessmentResult.user_id == user.id)
        .order_by(AssessmentResult.id.desc())
    )
    if result and result.recommended_jobs_json:
        top = (result.recommended_jobs_json.get("jobs") or [{}])[0]
        jname = top.get("job_name")
        if jname:
            job = db.scalar(select(Job).where(Job.job_name == jname))
            if job is not None:
                return job
    raise HTTPException(status_code=400, detail="未找到目标岗位，请先完成测评或指定 job_id")


def _user_status_map(db: Session, user_id: int) -> Dict[int, UserSkillStatus]:
    return {
        s.skill_node_id: s
        for s in db.scalars(
            select(UserSkillStatus).where(UserSkillStatus.user_id == user_id)
        ).all()
    }


def _refresh_path_status(db: Session, path: LearningPath) -> None:
    """联动：把路径节点状态落库（completed 推进 current_node 指针）。"""
    db.flush()
    rows = db.scalars(
        select(LearningPathNode)
        .where(LearningPathNode.path_id == path.id)
        .order_by(LearningPathNode.order_no.asc())
    ).all()
    progress_map = compute_progress_map(db, path.user_id, path.id)

    next_unfinished: Optional[LearningPathNode] = None
    all_done = True
    for r in rows:
        sk = db.get(SkillNode, r.skill_node_id)
        prereqs = list(sk.prerequisites_json or []) if sk else []
        mastered_names = {
            x.name for x in db.scalars(
                select(SkillNode).where(
                    SkillNode.id.in_([y.skill_node_id for y in rows])
                )
            ).all() if progress_map.get(x.id, 0) >= 80
        }
        pct = progress_map.get(r.skill_node_id, 0)
        if pct >= 80:
            r.status = NODE_COMPLETED
        elif pct > 0:
            r.status = "learning"
        elif all(p in mastered_names for p in prereqs):
            r.status = "unlocked"
        else:
            r.status = "locked"
        db.add(r)
        if pct < 80:
            all_done = False
            if next_unfinished is None:
                next_unfinished = r

    if next_unfinished is not None:
        path.current_node_id = next_unfinished.id
        path.status = PATH_ACTIVE
    else:
        path.current_node_id = rows[-1].id if rows else None
        path.status = PATH_COMPLETED
    db.add(path)
    db.commit()


# -------------------------------------------------------------------- #
# 生成学习路径
# -------------------------------------------------------------------- #
@path_router.post(
    "/generate",
    response_model=ApiResponse[GeneratePathOut],
    summary="生成个性化学习路径",
    description="基于画像目标岗位/技能短板/重要度/前置知识生成分段路径(青铜→王者)，Learning Agent 增强名称与段位目标。",
)
async def generate_learning_path(
    payload: GeneratePathIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """规划 + Agent 增强 + 落库（同岗位已有进行中路径时复用或强制重建）。"""
    job = _resolve_target_job(db, user, payload.job_id, payload.job_name)

    # 已有进行中路径：非 force 直接返回（避免重复生成）
    existing = db.scalars(
        select(LearningPath).where(
            LearningPath.user_id == user.id,
            LearningPath.status == PATH_ACTIVE,
        )
    ).all()
    if existing and not payload.force:
        path = existing[0]
        set_user_status_map(_user_status_map(db, user.id))
        m = build_path_map(db, path, compute_progress_map(db, user.id, path.id))
        meta = {
            "job_name": path.target_job,
            "reused": True,
            "skill_count": m["total_nodes"],
            "gap_count": m["total_nodes"] - m["mastered_nodes"],
        }
        return success(GeneratePathOut(path=m, meta=meta))

    # 规则规划
    plan, meta = plan_path(db, job, user.id)
    path_name, stage_options = await enhance_with_learning_agent(
        job.job_name, plan, meta
    )

    # 落库（新路径；旧进行中路径标记为 completed 归档）
    for old in existing:
        old.status = PATH_COMPLETED
        db.add(old)

    path = LearningPath(
        user_id=user.id,
        target_job=job.job_name,
        path_name=path_name,
        status=PATH_ACTIVE,
    )
    db.add(path)
    db.flush()

    for idx, item in enumerate(plan, start=1):
        db.add(
            LearningPathNode(
                path_id=path.id,
                skill_node_id=item["skill_node_id"],
                stage=item["stage"],
                order_no=idx,
                status=item["gap"] > 0 and "locked" or "unlocked",
                estimated_hours=item["estimated_hours"],
                prerequisites_json=item["prerequisites"],
            )
        )
    db.commit()

    _refresh_path_status(db, path)
    db.refresh(path)
    set_user_status_map(_user_status_map(db, user.id))
    map_data = build_path_map(db, path, compute_progress_map(db, user.id, path.id))

    return success(
        GeneratePathOut(
            path=map_data,
            meta={
                "job_name": job.job_name,
                "job_family": job.job_family,
                "skill_count": meta["skill_count"],
                "gap_count": meta["gap_count"],
                "total_hours": meta["total_hours"],
                "stages": meta["stages"],
                "agent_note": "Learning Agent 增强已启用"
                if llm_service.is_configured
                else "规则模板生成（LLM 未配置）",
            },
        )
    )


# -------------------------------------------------------------------- #
# 当前路径
# -------------------------------------------------------------------- #
@path_router.get(
    "/current",
    response_model=ApiResponse[Optional[LearningPathMapOut]],
    summary="当前学习路径",
)
def get_current_path(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """无进行中路径时 data=null。"""
    path = db.scalar(
        select(LearningPath)
        .where(LearningPath.user_id == user.id, LearningPath.status == PATH_ACTIVE)
        .order_by(LearningPath.id.desc())
    )
    if path is None:
        return {"code": 0, "message": "success", "data": None}
    set_user_status_map(_user_status_map(db, user.id))
    return success(
        build_path_map(db, path, compute_progress_map(db, user.id, path.id))
    )


# -------------------------------------------------------------------- #
# 路径地图
# -------------------------------------------------------------------- #
@path_router.get(
    "/{path_id}/map",
    response_model=ApiResponse[LearningPathMapOut],
    summary="学习路径分段地图",
)
def get_path_map(
    path_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """路径地图（青铜→王者 6 段）含全部节点状态与断点。"""
    path = db.get(LearningPath, path_id)
    if path is None or path.user_id != user.id:
        raise HTTPException(status_code=404, detail="学习路径不存在")
    set_user_status_map(_user_status_map(db, user.id))
    return success(
        build_path_map(db, path, compute_progress_map(db, user.id, path.id))
    )


# -------------------------------------------------------------------- #
# 更新进度 + 断点位置
# -------------------------------------------------------------------- #
@progress_router.put(
    "",
    response_model=ApiResponse[UpdateProgressOut],
    summary="更新节点学习进度",
    description="更新进度百分比与断点位置；进度>=80 自动推进当前节点指针，全部完成则路径置为 completed。",
)
def update_progress(
    payload: UpdateProgressIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """更新节点进度 + 同步 user_skill_status（掌握度=进度）。"""
    path = db.get(LearningPath, payload.path_id)
    if path is None or path.user_id != user.id:
        raise HTTPException(status_code=404, detail="学习路径不存在")
    node = db.scalar(
        select(LearningPathNode).where(
            LearningPathNode.path_id == path.id,
            LearningPathNode.skill_node_id == payload.skill_node_id,
        )
    )
    if node is None:
        raise HTTPException(status_code=404, detail="路径中不存在该技能节点")

    pct = max(0, min(100, payload.progress_percent))
    row = db.scalar(
        select(LearningProgress).where(
            LearningProgress.user_id == user.id,
            LearningProgress.path_id == path.id,
            LearningProgress.node_id == node.id,
        )
    )
    if row is None:
        row = LearningProgress(
            user_id=user.id, path_id=path.id, node_id=node.id
        )
        db.add(row)
    row.progress_percent = pct
    if payload.last_position is not None:
        row.last_position = payload.last_position
    db.add(row)

    # 同步掌握状态（rule：进度>=80 视为已掌握）
    status_row = db.scalar(
        select(UserSkillStatus).where(
            UserSkillStatus.user_id == user.id,
            UserSkillStatus.skill_node_id == payload.skill_node_id,
        )
    )
    from app.models.skill import STATUS_MASTERED, STATUS_LEARNING, STATUS_NOT_STARTED

    if status_row is None:
        status_row = UserSkillStatus(
            user_id=user.id, skill_node_id=payload.skill_node_id
        )
        db.add(status_row)
    status_row.mastery_score = pct
    status_row.status = (
        STATUS_MASTERED if pct >= 80 else (STATUS_LEARNING if pct > 0 else STATUS_NOT_STARTED)
    )
    db.add(status_row)

    _refresh_path_status(db, path)
    db.refresh(path)

    set_user_status_map(_user_status_map(db, user.id))
    map_data = build_path_map(db, path, compute_progress_map(db, user.id, path.id))
    updated_node = next(
        (n for stg in map_data["stages"].values() for n in stg if n["skill_node_id"] == payload.skill_node_id),
        None,
    )
    return success(
        UpdateProgressOut(
            path=map_data,
            updated_node=updated_node,
            to_next=pct >= 80,
        )
    )


# -------------------------------------------------------------------- #
# 断点续学
# -------------------------------------------------------------------- #
@progress_router.post(
    "/resume",
    response_model=ApiResponse[ResumePathOut],
    summary="断点续学",
    description="返回当前进行中路径的最近学习节点与上次位置，供前端一键跳转。",
)
def resume_learning(
    payload: ResumeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """定位断点：current_node_id 指向最近未完成的节点 + last_position。"""
    if payload.path_id:
        path = db.get(LearningPath, payload.path_id)
        if path is None or path.user_id != user.id:
            raise HTTPException(status_code=404, detail="学习路径不存在")
    else:
        path = db.scalar(
            select(LearningPath)
            .where(LearningPath.user_id == user.id, LearningPath.status == PATH_ACTIVE)
            .order_by(LearningPath.id.desc())
        )
        if path is None:
            return success(
                ResumePathOut(
                    path=_empty_map(),
                    resume_node=None,
                    resume_position=None,
                    hint="暂无进行中的学习路径，请先生成学习路径。",
                )
            )

    set_user_status_map(_user_status_map(db, user.id))
    map_data = build_path_map(db, path, compute_progress_map(db, user.id, path.id))

    resume_node = None
    resume_position = None
    if map_data["current_node_id"]:
        for stg in map_data["stages"].values():
            for n in stg:
                if n["id"] == map_data["current_node_id"]:
                    resume_node = n
                    resume_position = n.get("last_position") or None
                    break
            if resume_node:
                break
    if resume_node and not resume_position:
        # current 节点尚未开始（无断点），回退到该路径最近有学习位置的节点
        from app.models import LearningProgress as _LP

        last = db.scalar(
            select(_LP)
            .where(
                _LP.user_id == user.id,
                _LP.path_id == path.id,
                _LP.last_position.isnot(None),
                _LP.last_position != "",
            )
            .order_by(_LP.id.desc())
        )
        if last is not None:
            resume_position = last.last_position
    if resume_node:
        hint = "已定位到上次学习位置，点击继续学习。"
        if resume_position:
            hint = f"继续于「{resume_position}」，点击回到上次学习位置。"
    else:
        hint = "路径尚未开始，从第一关开始吧！"

    return success(
        ResumePathOut(
            path=map_data,
            resume_node=resume_node,
            resume_position=resume_position,
            hint=hint,
        )
    )


def _empty_map() -> Dict[str, Any]:
    from app.models.learning_path import STAGES

    return {
        "path_id": 0,
        "target_job": "",
        "path_name": "",
        "status": "",
        "current_node_id": None,
        "total_nodes": 0,
        "mastered_nodes": 0,
        "overall_progress": 0,
        "stages": {s: [] for s in STAGES},
        "stage_order": STAGES,
    }


# -------------------------------------------------------------------- #
# 资源推荐
# -------------------------------------------------------------------- #
@resource_router.get(
    "/recommend",
    response_model=ApiResponse[List[Dict[str, Any]]],
    summary="推荐学习资源",
    description="按当前节点（缺省取路径当前节点）规则评分推荐资源并持久化推荐记录。",
)
def recommend(
    skill_node_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    limit: int = 8,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """资源推荐：规则评分（节点匹配/难度/时长/类型）+ 落库推荐记录。"""
    target_id = skill_node_id
    if target_id is None:
        path = db.scalar(
            select(LearningPath)
            .where(LearningPath.user_id == user.id, LearningPath.status == PATH_ACTIVE)
            .order_by(LearningPath.id.desc())
        )
        if path is not None and path.current_node_id:
            node = db.get(LearningPathNode, path.current_node_id)
            if node is not None:
                target_id = node.skill_node_id
    if target_id is None:
        raise HTTPException(status_code=404, detail="当前没有可推荐资源的节点")

    resources = recommend_resources(
        db,
        user.id,
        target_id,
        limit=max(1, min(20, limit)),
        resource_type=resource_type,
    )
    return success(resources)