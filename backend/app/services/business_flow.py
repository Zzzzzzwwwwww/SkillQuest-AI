"""
SkillQuest AI 业务闭环编排服务（模块8）

闭环3：用户选定岗位后自动生成技能图谱 + 学习路径。
流程：upsert 画像 target_job → 回写学习档案/个人资料 → 规则规划分段路径 →
      Learning Agent 增强名称(可选) → 落库并刷新节点状态（全部复用模块4/5 服务）。
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, SkillNode, UserPersona, UserSkillStatus
from app.models.learning_path import (
    NODE_COMPLETED,
    PATH_ACTIVE,
    PATH_COMPLETED,
    LearningPath,
    LearningPathNode,
)
from app.models.user import User
from app.services.learning_path_service import (
    build_path_map,
    compute_progress_map,
    enhance_with_learning_agent,
    plan_path,
    set_user_status_map,
)
from app.services.llm import llm_service
from app.services.persona_auto import sync_target_job_to_archive


def _upsert_persona_target(job: Job, db: Session, user: User) -> UserPersona:
    """把用户选定的岗位写入画像（无画像则创建空骨架）。"""
    persona = db.scalar(select(UserPersona).where(UserPersona.user_id == user.id))
    if persona is None:
        persona = UserPersona(
            user_id=user.id,
            persona_tags_json={"tags": [], "summary": "", "strengths": [],
                               "weaknesses": [], "advice": "", "ai_enriched": False},
            ability_radar_json={"dimensions": []},
            learning_goal="围绕目标岗位「{}」补齐核心技能差距。".format(job.job_name),
        )
        db.add(persona)
    persona.target_job = job.job_name
    db.flush()
    return persona


def select_target_job(db: Session, user: User, job: Job) -> Dict[str, Any]:
    """用户选定目标岗位：画像 / 学习档案 / 个人资料三处同步落库。"""
    persona = _upsert_persona_target(job, db, user)
    sync_target_job_to_archive(db, user.id, job.job_name)

    from app.models.profile import UserProfile

    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if profile is not None and not profile.job_intention:
        profile.job_intention = job.job_name

    return {
        "target_job": job.job_name,
        "persona_created": (persona.persona_tags_json or {}).get("tags") or [],
    }


def _refresh_node_statuses(db: Session, path: LearningPath, user_id: int) -> None:
    """刷新路径节点状态与 current_node 指针（与模块5 逻辑一致）。"""
    db.flush()
    rows = db.scalars(
        select(LearningPathNode)
        .where(LearningPathNode.path_id == path.id)
        .order_by(LearningPathNode.order_no.asc())
    ).all()
    progress = compute_progress_map(db, user_id, path.id)

    nodes = db.scalars(
        select(SkillNode).where(
            SkillNode.id.in_([r.skill_node_id for r in rows])
        )
    ).all()
    node_by_id = {n.id: n for n in nodes}
    mastered = {
        x.id for x in nodes if progress.get(x.id, 0) >= 80
    }
    all_done = True
    next_node: Optional[LearningPathNode] = None
    for r in rows:
        node = node_by_id.get(r.skill_node_id)
        prereqs = list(node.prerequisites_json or []) if node else []
        prereq_names = {
            n.name for n in nodes if n.name in prereqs
        }
        pct = progress.get(r.skill_node_id, 0)
        if pct >= 80:
            r.status = NODE_COMPLETED
        elif pct > 0:
            r.status = "learning"
        else:
            unlocked = all(
                pname in {n.name for n in nodes if n.id in mastered}
                for pname in prereq_names
            )
            r.status = "unlocked" if unlocked else "locked"
        db.add(r)
        if pct < 80:
            all_done = False
            if next_node is None:
                next_node = r

    if next_node is not None:
        path.current_node_id = next_node.id
        path.status = PATH_ACTIVE
    else:
        path.current_node_id = rows[-1].id if rows else None
        path.status = PATH_COMPLETED
    db.add(path)


async def auto_generate_learning_path(
    db: Session, user: User, job: Job, force: bool = False
) -> Dict[str, Any]:
    """选定岗位后自动生成学习路径（复用模块5 规则规划 + Agent 增强）。

    Returns:
        {"path": 路径地图, "meta": 生成元信息}
    """
    existing = db.scalars(
        select(LearningPath).where(
            LearningPath.user_id == user.id,
            LearningPath.status == PATH_ACTIVE,
        )
    ).all()
    if existing and not force:
        path = existing[0]
        set_user_status_map(_user_status_map(db, user.id))
        return {
            "path": build_path_map(db, path, compute_progress_map(db, user.id, path.id)),
            "meta": {"job_name": path.target_job, "reused": True},
        }

    plan, meta = plan_path(db, job, user.id)
    path_name, stage_options = await enhance_with_learning_agent(
        job.job_name, plan, meta
    )

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
    db.flush()
    _refresh_node_statuses(db, path, user.id)
    db.commit()
    db.refresh(path)
    set_user_status_map(_user_status_map(db, user.id))
    map_data = build_path_map(db, path, compute_progress_map(db, user.id, path.id))

    return {
        "path": map_data,
        "meta": {
            "job_name": job.job_name,
            "job_family": job.job_family,
            "skill_count": meta["skill_count"],
            "gap_count": meta["gap_count"],
            "total_hours": meta["total_hours"],
            "stages": meta["stages"],
            "agent_note": "Learning Agent 增强已启用" if llm_service.is_configured
            else "规则模板生成（LLM 未配置）",
        },
    }


def _user_status_map(db: Session, user_id: int) -> Dict[int, UserSkillStatus]:
    return {
        s.skill_node_id: s
        for s in db.scalars(
            select(UserSkillStatus).where(UserSkillStatus.user_id == user_id)
        ).all()
    }