"""
SkillQuest AI 岗位技能图谱服务（模块4）

设计原则（第1条）：掌握状态、掌握度、Skill Gap、整体匹配度全部规则计算，AI 不参与。

职责：
  - 掌握状态推导（mastery_score → mastered/learning/not_started）
  - 岗位分层技能树构建（岗位 → 能力域 → 技能 → 知识点）
  - Skill Gap 分析（行业/岗位要求 vs 我的能力）
  - 技能详情推荐资源（规则化推荐，不依赖课程库）
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.skill import (
    JOB_ACTIVE,
    Job,
    JobSkillRelation,
    NODE_CAPABILITY,
    NODE_KNOWLEDGE,
    NODE_SKILL,
    STATUS_LEARNING,
    STATUS_MASTERED,
    STATUS_NOT_STARTED,
    SkillNode,
    UserSkillStatus,
)

# -------------------------------------------------------------------- #
# 常量与标签
# -------------------------------------------------------------------- #
MASTERED_THRESHOLD = 80  # 掌握度 >= 80 视为已掌握（规则）

STATUS_LABELS: Dict[str, str] = {
    STATUS_MASTERED: "已掌握",
    STATUS_LEARNING: "学习中",
    STATUS_NOT_STARTED: "未掌握",
}

NODE_TYPE_LABELS: Dict[str, str] = {
    NODE_CAPABILITY: "能力域",
    NODE_SKILL: "技能",
    NODE_KNOWLEDGE: "知识点",
}

# 节点与掌握状态的颜色（前端展示，后端同步字段供校验/文档）
NODE_COLORS: Dict[str, str] = {
    STATUS_MASTERED: "#22c55e",     # 绿：已掌握
    STATUS_LEARNING: "#f59e0b",     # 黄：学习中
    STATUS_NOT_STARTED: "#9ca3af",  # 灰：未掌握
}


# -------------------------------------------------------------------- #
# 状态规则推导
# -------------------------------------------------------------------- #
def infer_status(mastery_score: int) -> str:
    """由掌握度推导掌握状态（规则）：
      - 0          -> not_started（未掌握）
      - 1 ~ 79     -> learning（学习中）
      - >= 80      -> mastered（已掌握）
    """
    score = int(mastery_score or 0)
    if score <= 0:
        return STATUS_NOT_STARTED
    if score < MASTERED_THRESHOLD:
        return STATUS_LEARNING
    return STATUS_MASTERED


def normalize_status(status: Optional[str], mastery_score: int) -> str:
    """显式状态与掌握度对齐：显式状态优先，否则按掌握度规则推导。"""
    if status in (STATUS_MASTERED, STATUS_LEARNING, STATUS_NOT_STARTED):
        return status
    return infer_status(mastery_score)


# -------------------------------------------------------------------- #
# 用户掌握状态
# -------------------------------------------------------------------- #
def get_user_status_map(
    db: Session, user_id: int
) -> Dict[int, UserSkillStatus]:
    """加载用户全部技能掌握状态，返回 {skill_node_id: status}。"""
    rows = db.scalars(
        select(UserSkillStatus).where(UserSkillStatus.user_id == user_id)
    ).all()
    return {r.skill_node_id: r for r in rows}


# -------------------------------------------------------------------- #
# 技能树构建
# -------------------------------------------------------------------- #
class SkillTreeBuilder:
    """岗位技能树构建器（含用户掌握状态标注）。"""

    def __init__(self, db: Session, user_id: Optional[int]) -> None:
        self.db = db
        self.user_id = user_id
        self.status_map: Dict[int, UserSkillStatus] = (
            get_user_status_map(db, user_id) if user_id else {}
        )
        # 节点缓存：id -> SkillNode
        self._node_cache: Dict[int, SkillNode] = {}

    def load_nodes(self, ids: List[int]) -> Dict[int, SkillNode]:
        """按 id 集合加载节点并填充缓存。"""
        missing = [i for i in ids if i not in self._node_cache]
        if missing:
            rows = self.db.scalars(
                select(SkillNode).where(SkillNode.id.in_(missing))
            ).all()
            for node in rows:
                self._node_cache[node.id] = node
        return {i: self._node_cache[i] for i in ids if i in self._node_cache}

    def _children_of(self, parent_id: Optional[int]) -> List[SkillNode]:
        return self.db.scalars(
            select(SkillNode)
            .where(SkillNode.parent_id == parent_id)
            .order_by(SkillNode.importance.desc(), SkillNode.id.asc())
        ).all()

    def _decorate(
        self,
        node: SkillNode,
        required: Optional[int] = None,
        importance: Optional[int] = None,
    ) -> Dict[str, Any]:
        """把节点装饰为出参结构（含掌握状态/掌握度）。"""
        status = self.status_map.get(node.id)
        mastery = status.mastery_score if status else 0
        return {
            "id": node.id,
            "name": node.name,
            "level": node.level,
            "node_type": node.node_type,
            "node_type_label": NODE_TYPE_LABELS.get(node.node_type, node.node_type),
            "description": node.description or "",
            "importance": importance if importance is not None else node.importance,
            "required_level": required,
            "status": status.status if status else infer_status(mastery),
            "mastery_score": mastery,
            "prerequisites": list(node.prerequisites_json or []),
            "children": [],
        }

    def _subtree(self, node: SkillNode, required: Optional[int] = None) -> Dict[str, Any]:
        out = self._decorate(node, required=required, importance=node.importance)
        children = self._children_of(node.id)
        out["children"] = [self._subtree(c) for c in children]
        return out

    def build(self, job: Job) -> Dict[str, Any]:
        """构建岗位分层技能树：job -> 能力域 -> 技能 -> 知识点。

        树根为 job；level1 能力域由其下所有被岗位关联的技能节点的祖先聚合而来，
        岗位要求(required_level / importance)标注在被 relation 直接关联的节点上。
        """
        rels = self.db.scalars(
            select(JobSkillRelation).where(JobSkillRelation.job_id == job.id)
        ).all()
        if not rels:
            return self._decorate(
                SkillNode(id=job.id, name=job.job_name, level=0,
                          node_type="job", description=job.description or "",
                          importance=0, prerequisites_json=[]),
            )

        # relation 目标节点（须为 level2 技能或更深；若为能力域则单独处理）
        targets = self.load_nodes([r.skill_node_id for r in rels])
        rel_by_node = {r.skill_node_id: r for r in rels}

        # 找每个 target 所属的能力域祖先（level==1）
        cap_of_target: Dict[int, int] = {}
        for t in targets.values():
            cap_id = find_level_ancestor(self, t, 1)
            if cap_id is not None:
                cap_of_target[t.id] = cap_id

        # 能力域节点集合（含 relation 直接指向能力域的情况）
        cap_node_ids = set(cap_of_target.values())
        for tid, t in targets.items():
            if t.node_type == NODE_CAPABILITY:
                cap_node_ids.add(tid)
        caps = self.load_nodes(list(cap_node_ids))

        root = self._decorate(
            SkillNode(id=job.id, name=job.job_name, level=0,
                      node_type="job", description=job.description or "",
                      importance=0, prerequisites_json=[]),
        )

        # 组装：能力域 -> 其下关联技能（含 required/importance）-> 知识点子树
        cap_children: Dict[int, List[Dict[str, Any]]] = {}
        for cap_id in caps:
            cap_children.setdefault(cap_id, [])

        for tid, t in targets.items():
            rel = rel_by_node[t.id]
            item = self._decorate(
                t,
                required=rel.required_level,
                importance=rel.importance,
            )
            item["children"] = [
                self._subtree(c) for c in self._children_of(t.id)
            ]
            if t.node_type == NODE_CAPABILITY:
                # relation 直接挂在能力域上：整棵子树都支持
                item["children"] = [self._subtree(c) for c in self._children_of(t.id)]
            cap_id = cap_of_target.get(t.id)
            if cap_id is not None and cap_id != t.id:
                cap_children.setdefault(cap_id, []).append(item)
            elif t.node_type == NODE_CAPABILITY:
                cap_children.setdefault(t.id, []).append(item)
            elif cap_id is None:
                # 无法归类的顶层节点直接挂到能力域分组 "其他"
                cap_children.setdefault(-1, []).append(item)

        # 构建能力域出参（importance=子技能均值或节点 importance）
        for cap in caps.values():
            kids = cap_children.get(cap.id) or []
            importance = int(
                sum(k["importance"] for k in kids) / len(kids)
            ) if kids else cap.importance
            cap_out = self._decorate(cap, importance=importance)
            cap_out["children"] = kids
            root["children"].append(cap_out)

        # 无法分组到能力域的（极少）附加在末尾
        orphans = cap_children.get(-1) or []
        if orphans and not caps:
            root["children"] = orphans

        return root


def find_level_ancestor(builder: SkillTreeBuilder, node: SkillNode, level: int) -> Optional[int]:
    """沿 parent 链向上找指定层级的节点（能力域=level 1）。"""
    seen: set = set()
    current = node
    while current is not None and current.id not in seen:
        seen.add(current.id)
        if current.level == level and current.node_type == NODE_CAPABILITY:
            return current.id
        if current.parent_id is None:
            return None
        current = builder.load_nodes([current.parent_id]).get(current.parent_id)
    return None


# -------------------------------------------------------------------- #
# Skill Gap 分析（行业/岗位要求 vs 我的能力）
# -------------------------------------------------------------------- #
def compute_skill_gaps(
    db: Session, job: Job, user_id: Optional[int] = None
) -> Dict[str, Any]:
    """计算岗位所需的技能级 Gap 与整体胜任度（规则）。

    Returns:
      {
        "overall_mastery": 0-100 加权平均掌握度,
        "fit_rate": 0-100 加权达到率（min(mastery/required,1)）,
        "skill_count": 岗位要求技能数,
        "mastered_count": 已达标技能数,
        "gaps": [{skill_id, name, importance, required, mastery, gap}]
      }
    """
    status_map = get_user_status_map(db, user_id) if user_id else {}
    rels = db.scalars(
        select(JobSkillRelation).where(JobSkillRelation.job_id == job.id)
    ).all()
    skills = db.scalars(
        select(SkillNode).where(
            SkillNode.id.in_([r.skill_node_id for r in rels]) if rels else False
        )
    ).all()
    skill_by_id = {s.id: s for s in skills}

    items: List[Dict[str, Any]] = []
    total_w = 0
    weighted_mastery = 0.0
    weighted_fit = 0.0
    mastered_count = 0

    for rel in rels:
        node = skill_by_id.get(rel.skill_node_id)
        if node is None:
            continue
        w = max(rel.importance, 1)
        st = status_map.get(node.id)
        m = int(st.mastery_score or 0) if st else 0
        required = int(rel.required_level or 0)
        total_w += w
        weighted_mastery += w * m
        fit = min(m / required, 1.0) if required > 0 else (1.0 if m >= MASTERED_THRESHOLD else 0.0)
        weighted_fit += w * fit
        if required > 0 and m >= required:
            mastered_count += 1
        items.append(
            {
                "skill_id": node.id,
                "name": node.name,
                "importance": rel.importance,
                "required": required,
                "mastery": m,
                "gap": round(max(0.0, required - m), 1),
            }
        )

    items.sort(key=lambda x: (x["gap"] > 0, -x["importance"]), reverse=True)
    return {
        "overall_mastery": round(weighted_mastery / total_w, 1) if total_w else 0.0,
        "fit_rate": round(weighted_fit / total_w * 100, 1) if total_w else 0.0,
        "skill_count": len(items),
        "mastered_count": mastered_count,
        "gaps": items,
    }


# -------------------------------------------------------------------- #
# 技能详情 / 推荐资源（规则化）
# -------------------------------------------------------------------- #
RECOMMENDED_RESOURCE_TEMPLATES: List[Dict[str, str]] = [
    {"type": "入门", "title": "{name} 入门教程"},
    {"type": "实战", "title": "{name} 实战练习"},
    {"type": "知识", "title": "《{name}》进阶资料"},
]


def build_skill_detail(
    db: Session, node: SkillNode, user_id: Optional[int] = None
) -> Dict[str, Any]:
    """技能详情：基础信息 + 前置知识 + 推荐资源 + 关联岗位与要求。"""
    status_map = get_user_status_map(db, user_id) if user_id else {}
    st = status_map.get(node.id)
    mastery = int(st.mastery_score or 0) if st else 0

    # 前置知识详情（按名称匹配同层级/父级节点）
    prereq_names = list(node.prerequisites_json or [])
    prereq_nodes = db.scalars(
        select(SkillNode).where(SkillNode.name.in_(prereq_names))
    ).all() if prereq_names else []
    prereqs = [
        {
            "id": p.id,
            "name": p.name,
            "node_type": p.node_type,
            "mastery": int(
                status_map[p.id].mastery_score or 0
            ) if p.id in status_map else 0,
            "status": status_map[p.id].status if p.id in status_map else infer_status(0),
        }
        for p in prereq_nodes
    ]
    # 未入库的前置名也展示（占位）
    known_names = {p["name"] for p in prereqs}
    for name in prereq_names:
        if name not in known_names:
            prereqs.append(
                {"id": None, "name": name, "node_type": "skill",
                 "mastery": 0, "status": STATUS_NOT_STARTED}
            )

    # 关联岗位（规则：按 importance 降序）
    rows = db.execute(
        select(Job, JobSkillRelation)
        .join(JobSkillRelation, JobSkillRelation.job_id == Job.id)
        .where(JobSkillRelation.skill_node_id == node.id, Job.status == JOB_ACTIVE)
        .order_by(JobSkillRelation.importance.desc())
    ).all()
    related_jobs = [
        {
            "job_id": job.id,
            "job_name": job.job_name,
            "job_family": job.job_family,
            "importance": rel.importance,
            "required_level": rel.required_level,
        }
        for job, rel in rows
    ]

    resources = [
        {"type": t["type"], "title": t["title"].format(name=node.name), "desc": _resource_desc(node, t["type"])}
        for t in RECOMMENDED_RESOURCE_TEMPLATES
    ]

    return {
        "id": node.id,
        "name": node.name,
        "node_type": node.node_type,
        "node_type_label": NODE_TYPE_LABELS.get(node.node_type, node.node_type),
        "level": node.level,
        "description": node.description or "",
        "importance": node.importance,
        "mastery_score": mastery,
        "status": st.status if st else infer_status(mastery),
        "prerequisites": prereqs,
        "resources": resources,
        "related_jobs": related_jobs,
    }


def _resource_desc(node: SkillNode, rtype: str) -> str:
    if node.node_type == NODE_KNOWLEDGE:
        base = "围绕知识点「{}」学习概念与应用场景".format(node.name)
    elif node.node_type == NODE_SKILL:
        base = "围绕技能「{}」开展系统训练与项目实践".format(node.name)
    else:
        base = "围绕能力域「{}」分层递进学习".format(node.name)
    if rtype == "入门":
        return base + "，先建立整体认知（预计 1-2 天）"
    if rtype == "实战":
        return base + "，配合小任务巩固（预计 2-3 天）"
    return base + "，形成系统性知识体系（建议每周复盘）"



# -------------------------------------------------------------------- #
# 技能树查询工具（供接口复用）
# -------------------------------------------------------------------- #
def find_node_by_id(db: Session, node_id: int) -> Optional[SkillNode]:
    return db.get(SkillNode, node_id)