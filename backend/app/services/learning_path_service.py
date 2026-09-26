"""
SkillQuest AI 个性化学习路径服务（模块5）

设计原则（第1条）：能规则算的不用大模型 ——
  路径节点排序、段位分配、预计时长、进度推导、资源推荐评分全部规则计算；
  第3条：Learning Agent 仅对本段位目标/路径名称做生成性增强，
  LLM 未配置时自动降级为规则模板，前端体验不中断。

生成依据（用户提示）：
  - 用户画像（UserPersona.target_job / learning_goal）
  - 目标岗位（jobs + job_skill_relations 的 importance / required_level）
  - 技能短板（user_skill_status.mastery_score vs required_level 的 gap）
  - 前置知识（skill_nodes.prerequisites_json）
路径分段：青铜 → 白银 → 黄金 → 铂金 → 钻石 → 王者。
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.learning_path import (
    NODE_COMPLETED,
    NODE_LEARNING,
    NODE_LOCKED,
    NODE_UNLOCKED,
    PATH_ACTIVE,
    STAGES,
    STAGE_LABELS,
)
from app.models.skill import (
    Job,
    JobSkillRelation,
    NODE_CAPABILITY,
    NODE_KNOWLEDGE,
    NODE_SKILL,
    SkillNode,
    UserSkillStatus,
)
from app.services.agent_service import AgentInput, agent_service

# 各段位默认目标说明（规则模板，LLM 未配置时使用）
STAGE_OBJECTIVES: Dict[str, str] = {
    "bronze": "夯实基础：掌握入门技能与前置知识，建立岗位认知。",
    "silver": "巩固技能：完成核心工具与语言的系统训练。",
    "gold": "进阶实战：掌握岗位关键技能并完成小项目实践。",
    "platinum": "能力提升：突破难点技能，向岗位要求靠拢。",
    "diamond": "精进打磨：补齐遗留短板，逼近岗位胜任标准。",
    "king": "巅峰冲刺：突击最高要求技能，达成岗位胜任目标。",
}

# 难度/时长规则（skill knowledge 与 skill 可接受基础 60-90 分钟资源）
RESOURCE_TYPE_LABELS = {
    "video": "视频",
    "course": "课程",
    "article": "文章",
    "exercise": "练习",
}

# 技能节点默认估算时长基数（小时）：由重要度/层级推导
def _estimate_hours(node: SkillNode, importance: int) -> int:
    """按重要度与层级规则估算学习时长(小时)。"""
    base = 3 if node.node_type == NODE_KNOWLEDGE else 6
    w = importance if importance > 0 else node.importance
    return int(base + round(w * 0.12))


# -------------------------------------------------------------------- #
# 排序：前置知识优先 → 重要度降序（拓扑 + 权重）
# -------------------------------------------------------------------- #
def _topo_sort_skills(
    skills: List[SkillNode],
    name_index: Dict[str, SkillNode],
    weight_of: Dict[int, int],
) -> List[SkillNode]:
    """前置知识优先 + 同层按重要度降序的拓扑排序。

    原理：对被岗位关联的技能做 DFS 后序，把「前置技能」排到依赖技能之前；
    同一批可并行节点按重要度降序，让高重要度能力域任务更早出现。
    """
    ordered: List[SkillNode] = []
    visited: Dict[int, int] = {}  # 0=visiting, 1=done
    by_id: Dict[int, SkillNode] = {s.id: s for s in skills}

    def resolve_prereq(node: SkillNode) -> List[SkillNode]:
        """把 prerequisites_json 里的名称映射为真实技能节点（若在岗位技能内）。"""
        out: List[SkillNode] = []
        for name in (node.prerequisites_json or []):
            p = name_index.get(name)
            if p is not None and p.id in by_id:
                out.append(p)
        return out

    def dfs(node: SkillNode) -> None:
        if visited.get(node.id) == 1:
            return
        if visited.get(node.id) == 0:
            return  # 环保护
        visited[node.id] = 0
        for pre in resolve_prereq(node):
            dfs(pre)
        visited[node.id] = 1
        ordered.append(node)

    # 前置技能先排（它们往往更基础）
    todo = sorted(skills, key=lambda s: (weight_of.get(s.id, 0)), reverse=True)
    # 先处理被其他技能依赖的前置项，保证它们更早
    for s in todo:
        if any(
            t.id in by_id for t in resolve_prereq(s)
        ):
            dfs(s)
    for s in todo:
        dfs(s)
    return ordered


# -------------------------------------------------------------------- #
# 路径规划（规则）：技能短板 → 排序 → 分段位
# -------------------------------------------------------------------- #
def plan_path(
    db: Session, job: Job, user_id: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """规则规划一条学习路径。

    Returns:
        (plan_items, meta)
        plan_items: [
          {skill_node_id, name, node_type, capability, importance,
           required_level, mastery, gap, estimated_hours,
           prerequisites, stage}
        ] 已按学习顺序排列
        meta: {job_name, job_family, skill_count, gap_count,
               total_hours, stages: {stage: {count, objective, hours}}}
    """
    # ---- 岗位关联技能 ----（relation 直接关联技能级/能力域）
    rels = db.scalars(
        select(JobSkillRelation).where(JobSkillRelation.job_id == job.id)
    ).all()
    if not rels:
        raise ValueError("该岗位暂无关联技能，无法生成学习路径")

    nodes = db.scalars(
        select(SkillNode).where(
            SkillNode.id.in_([r.skill_node_id for r in rels])
        )
    ).all()
    node_by_id = {n.id: n for n in nodes}
    rel_by_node = {r.skill_node_id: r for r in rels}

    # 用户掌握状态（短板）
    status_map: Dict[int, UserSkillStatus] = {}
    if user_id:
        status_map = {
            s.skill_node_id: s
            for s in db.scalars(
                select(UserSkillStatus).where(UserSkillStatus.user_id == user_id)
            ).all()
        }

    # 能力域祖先（用于展示与辅助排序分组）
    cap_parents: Dict[int, Optional[str]] = {}
    for n in nodes:
        cap = _find_capability_name(db, n, node_by_id)
        cap_parents[n.id] = cap

    # ---- 权重 = 岗位重要度 + gap 权重（短板优先补）----
    weight_of: Dict[int, int] = {}
    for n in nodes:
        rel = rel_by_node[n.id]
        st = status_map.get(n.id)
        mastery = st.mastery_score if st else 0
        gap = max(0, int(rel.required_level or 0) - mastery)
        weight = int(rel.importance) + int(gap)  # 重要 + 缺口 → 决定排序权重
        weight_of[n.id] = weight

    # 取岗位技能集合（若 relation 直接指向能力域，展开其下技能）
    direct_skills = [n for n in nodes if n.node_type == NODE_SKILL]
    expanded: Dict[int, SkillNode] = {}
    for n in nodes:
        if n.node_type == NODE_CAPABILITY:
            for s in db.scalars(
                select(SkillNode).where(
                    SkillNode.parent_id == n.id, SkillNode.node_type == NODE_SKILL
                )
            ).all():
                expanded[s.id] = s
    skill_pool: Dict[int, SkillNode] = {}
    for s in direct_skills:
        skill_pool[s.id] = s
    for sid, s in expanded.items():
        skill_pool.setdefault(sid, s)

    # 前置名索引（在技能池内）
    name_index = {s.name: s for s in skill_pool.values()}
    pending: Dict[int, SkillNode] = {}
    for s in list(skill_pool.values()):
        for pre in (s.prerequisites_json or []):
            if pre not in name_index:
                # 前置名称未在池中（可能指向知识点），尝试全库解析后补权重
                ext = db.scalar(
                    select(SkillNode).where(SkillNode.name == pre)
                )
                if ext is not None:
                    pending.setdefault(ext.id, ext)
                    name_index[pre] = ext
    for pid, pnode in pending.items():
        skill_pool.setdefault(pid, pnode)

    pool = list(skill_pool.values())
    sorted_skills = _topo_sort_skills(pool, name_index, weight_of)

    # ---- 分段位：均分 6 段（青铜→王者），每段至少 1 个（若技能数 < 6 则段数=技能数） ----
    n = len(sorted_skills)
    bucket = min(6, n)
    per = math.ceil(n / bucket)
    plan: List[Dict[str, Any]] = []
    stage_stats: Dict[str, Dict[str, Any]] = {}

    for idx, s in enumerate(sorted_skills):
        stage = STAGES[min(idx // per if per > 0 else 0, 5)]
        rel = rel_by_node.get(s.id)
        importance = rel.importance if rel else s.importance
        required = rel.required_level if rel else 0
        st = status_map.get(s.id)
        mastery = st.mastery_score if st else 0
        gap = max(0.0, float(required - mastery))
        hours = _estimate_hours(s, importance)

        item = {
            "skill_node_id": s.id,
            "name": s.name,
            "node_type": s.node_type,
            "capability": cap_parents.get(s.id) or "",
            "importance": importance,
            "required_level": required,
            "mastery": mastery,
            "gap": gap,
            "estimated_hours": hours,
            "prerequisites": list(s.prerequisites_json or []),
            "stage": stage,
        }
        plan.append(item)

        stat = stage_stats.setdefault(
            stage, {"count": 0, "hours": 0, "objective": STAGE_OBJECTIVES.get(stage, "")}
        )
        stat["count"] += 1
        stat["hours"] += hours

    # 校验缺失段位：若技能少于6个，未启用的段位补占位（保持前端 6 段渲染）
    for stage in STAGES:
        stage_stats.setdefault(
            stage, {"count": 0, "hours": 0, "objective": STAGE_OBJECTIVES.get(stage, "")}
        )

    meta = {
        "job_name": job.job_name,
        "job_family": job.job_family,
        "skill_count": n,
        "gap_count": sum(1 for it in plan if it["gap"] > 0),
        "total_hours": sum(it["estimated_hours"] for it in plan),
        "stages": stage_stats,
    }
    return plan, meta


def _find_capability_name(
    db: Session, node: SkillNode, pool: Dict[int, SkillNode]
) -> Optional[str]:
    """沿 parent 链向上找能力域（level1），返回其名称。"""
    seen: set = set()
    cur: Optional[SkillNode] = node
    while cur is not None and cur.id not in seen:
        seen.add(cur.id)
        if cur.node_type == NODE_CAPABILITY:
            return cur.name
        if cur.parent_id is None:
            return None
        cur = db.get(SkillNode, cur.parent_id)
    return None


# -------------------------------------------------------------------- #
# Learning Agent 增强（可选；未配置 LLM 时规则降级）
# -------------------------------------------------------------------- #
async def enhance_with_learning_agent(
    job_name: str, plan: List[Dict[str, Any]], meta: Dict[str, Any]
) -> Tuple[str, Dict[str, str]]:
    """调用 Learning Agent（统一 AgentService）生成路径名称与各段位目标。
    失败/未配置时降级为规则模板。

    Returns:
        (path_name, stage_options)  stage_options: {stage: objective ...}
    """
    path_name = f"{job_name} · 成长进阶之路"
    fallback = {s: meta["stages"].get(s, {}).get("objective", STAGE_OBJECTIVES[s]) for s in STAGES}

    summary_lines = []
    for it in plan[:12]:
        summary_lines.append(
            "技能「{}」重要度{}，掌握{}/{}，缺口{}，前置：{}".format(
                it["name"], it["importance"], it["mastery"],
                it["required_level"], int(it["gap"]),
                "、".join(it["prerequisites"]) if it["prerequisites"] else "无",
            )
        )
    stage_hint = "、".join(
        "{}段({}项/{}h)".format(
            STAGE_LABELS[s], meta["stages"].get(s, {}).get("count", 0),
            meta["stages"].get(s, {}).get("hours", 0)
        ) for s in STAGES
    )

    result = await agent_service.run(
        AgentInput(
            agent_type="learning",
            user_context={
                "job_name": job_name,
                "plan_summary": summary_lines,
                "planned_stages": stage_hint,
            },
            max_tokens=1024,
        )
    )

    if result.degraded or not result.ok or not result.data:
        return path_name, fallback

    data = result.data
    new_name = str(data.get("goal") or path_name)[:60]
    options: Dict[str, str] = {}
    for idx, stage in enumerate(STAGES):
        stage_desc = "unknown"
        stages_data = data.get("stages") or []
        if idx < len(stages_data) and isinstance(stages_data[idx], dict):
            stage_desc = str(stages_data[idx].get("objective") or fallback[stage])
        options[stage] = stage_desc[:120]
    return new_name, options if len(options) == 6 else fallback


# -------------------------------------------------------------------- #
# 节点状态推导（规则）：解锁 / 完成联动
# -------------------------------------------------------------------- #
def derive_node_status(
    progress_map: Dict[int, int], prerequisites: List[str], mastered: set
) -> str:
    """根据进度与前置完成情况推导节点状态。"""
    pct = progress_map.get("_self", 0)
    if pct >= 80:
        return NODE_COMPLETED
    prereq_ok = all(name in mastered for name in prerequisites)
    if pct > 0:
        return NODE_LEARNING
    if prereq_ok:
        return NODE_UNLOCKED
    return NODE_LOCKED


def should_complete_path(plan: List[Dict[str, Any]], progress: Dict[int, int]) -> bool:
    """全部节点完成度达到阈值即视为路径完成（规则）。"""
    if not plan:
        return False
    return all(progress.get(it["skill_node_id"], 0) >= 80 for it in plan)


def compute_progress_map(db: Session, user_id: int, path_id: int) -> Dict[int, int]:
    """读取该用户路径下各 skill_node 的进度（0-100）。"""
    from app.models.learning_path import LearningPathNode, LearningProgress

    rows = db.scalars(
        select(LearningProgress).where(
            LearningProgress.user_id == user_id,
            LearningProgress.path_id == path_id,
        )
    ).all()
    node_ids = {r.node_id: r.progress_percent for r in rows}
    if not node_ids:
        return {}
    nodes = db.scalars(
        select(LearningPathNode).where(LearningPathNode.path_id == path_id)
    ).all()
    return {n.skill_node_id: node_ids.get(n.id, 0) for n in nodes}

# -------------------------------------------------------------------- #
# 路径地图组装（供 GET current / map 复用）
# -------------------------------------------------------------------- #
# -------------------------------------------------------------------- #
# 路径地图组装（供 GET current / map 复用）
# -------------------------------------------------------------------- #
def build_path_map(
    db: Session,
    path,
    progress_map: Dict[int, int],
    node_rows: Optional[List] = None,
) -> Dict[str, Any]:
    """把 learning_path + nodes 组装为前端地图结构（分 6 段）。

    节点字段补齐：技能名称/类型/能力域/岗位要求/掌握度/缺口/状态推导
    （状态规则：进度>=80 completed；>0 learning；前置全掌握 unlocked；否则 locked）。
    """
    from app.models.learning_path import LearningPathNode, LearningProgress

    if node_rows is None:
        node_rows = db.scalars(
            select(LearningPathNode)
            .where(LearningPathNode.path_id == path.id)
            .order_by(LearningPathNode.order_no.asc())
        ).all()
    if not node_rows:
        return {
            "path_id": path.id,
            "target_job": path.target_job,
            "path_name": path.path_name,
            "status": path.status,
            "current_node_id": path.current_node_id,
            "total_nodes": 0,
            "mastered_nodes": 0,
            "overall_progress": 0,
            "stages": {s: [] for s in STAGES},
            "stage_order": STAGES,
        }

    skill_ids = [r.skill_node_id for r in node_rows]
    skills = db.scalars(
        select(SkillNode).where(SkillNode.id.in_(skill_ids))
    ).all()
    skill_by_id = {s.id: s for s in skills}

    # 岗位要求（importance / required_level）映射
    job = db.scalar(select(Job).where(Job.job_name == path.target_job))
    req: Dict[int, Tuple[int, int]] = {}
    if job is not None:
        for rel in db.scalars(
            select(JobSkillRelation).where(JobSkillRelation.job_id == job.id)
        ).all():
            req[rel.skill_node_id] = (rel.importance, rel.required_level)

    # 已掌握技能名集合（用于解锁判定）
    mastered_names: set = set()
    for r in node_rows:
        sk = skill_by_id.get(r.skill_node_id)
        if sk is None or progress_map.get(r.skill_node_id, 0) < 80:
            continue
        mastered_names.add(sk.name)
        mastered_names.update(sk.prerequisites_json or [])

    cap_cache: Dict[int, str] = {}
    progress_rows = db.scalars(
        select(LearningProgress).where(
            LearningProgress.path_id == path.id
        )
    ).all()
    pos_by_node = {r.node_id: r.last_position for r in progress_rows}

    stage_nodes: Dict[str, List[Dict[str, Any]]] = {s: [] for s in STAGES}
    for r in node_rows:
        sk = skill_by_id.get(r.skill_node_id)
        pct = progress_map.get(r.skill_node_id, 0)
        prereqs = list(sk.prerequisites_json or []) if sk else []
        status = _derive_status(pct, prereqs, mastered_names)
        cap = _cap_name_cached(db, sk, cap_cache) if sk else ""
        imp, req_lv = req.get(r.skill_node_id, (0, 0))
        st = status_map_global().get(r.skill_node_id)
        mastery = st.mastery_score if st else 0
        gap = max(0.0, float(req_lv - mastery))
        stage_nodes.setdefault(r.stage, []).append({
            "id": r.id,
            "skill_node_id": r.skill_node_id,
            "name": sk.name if sk else "",
            "node_type": sk.node_type if sk else "",
            "capability": cap,
            "stage": r.stage,
            "order_no": r.order_no,
            "status": status,
            "estimated_hours": r.estimated_hours,
            "importance": imp,
            "required_level": req_lv,
            "mastery": mastery,
            "gap": gap,
            "progress_percent": pct,
            "last_position": pos_by_node.get(r.id) or "",
            "prerequisites": prereqs,
        })

    total = len(node_rows)
    mastered = sum(1 for x in node_rows if progress_map.get(x.skill_node_id, 0) >= 80)
    return {
        "path_id": path.id,
        "target_job": path.target_job,
        "path_name": path.path_name,
        "status": path.status,
        "current_node_id": path.current_node_id,
        "total_nodes": total,
        "mastered_nodes": mastered,
        "overall_progress": round(sum(progress_map.get(x.skill_node_id, 0) for x in node_rows) / total) if total else 0,
        "stages": stage_nodes,
        "stage_order": STAGES,
    }


_status_global: Dict[int, Any] = {}


def status_map_global() -> Dict[int, Any]:
    """供 build_path_map 读取的用户掌握状态（由接口填充）。"""
    return _status_global


def set_user_status_map(rows) -> None:
    """接口/测试注入用户掌握状态映射。"""
    _status_global.clear()
    if rows:
        _status_global.update(rows)


def _derive_status(pct: int, prerequisites: List[str], mastered_names: set) -> str:
    """节点状态推导（规则）。"""
    if pct >= 80:
        return NODE_COMPLETED
    if pct > 0:
        return NODE_LEARNING
    prereq_ok = all(n in mastered_names for n in prerequisites)
    if prereq_ok:
        return NODE_UNLOCKED
    return NODE_LOCKED


def _cap_name_cached(db: Session, node: SkillNode, cache: Dict[int, str]) -> str:
    """沿父链找能力域名（带缓存）。"""
    seen: set = set()
    cur: Optional[SkillNode] = node
    while cur is not None and cur.id not in seen:
        seen.add(cur.id)
        if cur.node_type == NODE_CAPABILITY:
            cache[node.id] = cur.name
            return cur.name
        if cur.parent_id is None:
            break
        cur = db.get(SkillNode, cur.parent_id)
    return cache.get(node.id, "")


def _last_position(db: Session, path_id: int, node_id: int) -> str:
    from app.models.learning_path import LearningProgress

    row = db.scalar(
        select(LearningProgress).where(
            LearningProgress.path_id == path_id,
            LearningProgress.node_id == node_id,
        )
    )
    return row.last_position if row else ""


# -------------------------------------------------------------------- #
# 资源推荐（规则评分）→ 持久化 resource_recommendations
# -------------------------------------------------------------------- #
def recommend_resources(
    db: Session,
    user_id: int,
    skill_node_id: int,
    limit: int = 8,
    resource_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """为技能/知识点节点推荐学习资源（规则排序）。

    评分逻辑：
      - 匹配关联节点（直接关联 + 若为技能节点则含其知识点）→ 基础分 60
      - 难度抑制：难度与资源时长适中 → 加分
      - 前置协同：节点属于同一能力域/技能 → 额外加分
      - 持久化推荐记录（含理由/评分），供断点续学与复盘复用。

    resource_type: 可选，按资源类型过滤（video/course/article/exercise）。
    """
    from app.models.learning_path import LearningResource, ResourceRecommendation
    from app.models.skill import SkillNode

    node = db.get(SkillNode, skill_node_id)
    if node is None:
        return []

    # 关联范围：知识节点→自身；技能→自身 + 子知识点；能力域→其下全部
    related_ids = {skill_node_id}
    if node.node_type == NODE_CAPABILITY:
        related_ids |= {
            s.id for s in db.scalars(
                select(SkillNode).where(SkillNode.parent_id == node.id)
            ).all()
        }
    elif node.node_type == NODE_SKILL:
        related_ids |= {
            s.id for s in db.scalars(
                select(SkillNode).where(
                    SkillNode.parent_id == node.id,
                    SkillNode.node_type == NODE_KNOWLEDGE,
                )
            ).all()
        }

    resources_stmt = select(LearningResource).where(
        LearningResource.skill_node_id.in_(related_ids)
    )
    if resource_type:
        resources_stmt = resources_stmt.where(LearningResource.type == resource_type)
    resources = db.scalars(resources_stmt).all()
    if not resources:
        return []

    scored: List[Dict[str, Any]] = []
    for r in resources:
        score = 60
        # 难度适中 + 时长适中加分
        if 1 <= r.difficulty <= 3:
            score += 15
        if 10 <= r.duration <= 180:
            score += 10
        # 直接关联加分
        if r.skill_node_id == skill_node_id:
            score += 15
        # 练习/视频在入门阶段更有性价比
        if r.type in ("exercise", "video"):
            score += 5
        reason = _build_reason(r, node, related_ids)
        scored.append(
            {
                "resource_id": r.id,
                "title": r.title,
                "type": r.type,
                "type_label": RESOURCE_TYPE_LABELS.get(r.type, r.type),
                "url": r.url,
                "skill_node_id": r.skill_node_id,
                "difficulty": r.difficulty,
                "duration": r.duration,
                "description": r.description or "",
                "reason": reason,
                "score": min(100, score),
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:limit]

    # 持久化推荐记录
    for rec in top:
        db.add(
            ResourceRecommendation(
                user_id=user_id,
                resource_id=rec["resource_id"],
                reason=rec["reason"],
                score=rec["score"],
            )
        )
    db.commit()
    return top


def _build_reason(resource, node, related_ids) -> str:
    if resource.skill_node_id == node.id:
        return "与当前学习节点「{}」直接匹配，建议优先学习。".format(node.name)
    if resource.skill_node_id in related_ids:
        return "属于「{}」能力范围，可与当前节点配套巩固。".format(node.name)
    return "与当前学习目标相关，可作为扩展补充。"
