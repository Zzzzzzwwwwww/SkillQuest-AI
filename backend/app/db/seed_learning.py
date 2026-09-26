"""
SkillQuest AI 学习资源种子数据（模块5）

为技能图谱中的技能/知识点生成规则化学习资源条目（视频/课程/文章/练习），
供「GET /learning-resources/recommend」规则评分后推荐。

资源 URL 使用课程平台演示地址（沙箱环境不可外联，仅演示结构）。
"""

from typing import Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.learning_path import (
    LearningResource,
    RESOURCE_ARTICLE,
    RESOURCE_COURSE,
    RESOURCE_EXERCISE,
    RESOURCE_VIDEO,
)
from app.models.skill import NODE_KNOWLEDGE, NODE_SKILL, SkillNode

# 资源标题模板：按技能/知识点 + 类型
_TEMPLATES: Dict[str, Tuple[str, int]] = {
    RESOURCE_VIDEO: ("【视频】{name} · 精讲速成", 1),
    RESOURCE_COURSE: ("【课程】{name} · 系统进阶", 2),
    RESOURCE_ARTICLE: ("【文章】{name} · 要点图解", 1),
    RESOURCE_EXERCISE: ("【练习】{name} · 实战刷题", 3),
}

_DESCS: Dict[str, str] = {
    RESOURCE_VIDEO: "跟随讲师快速建立概念认知，适合入门预热。",
    RESOURCE_COURSE: "成体系的章节课程，配合项目练习深入掌握。",
    RESOURCE_ARTICLE: "图文结合的知识要点总结，适合碎片时间复习。",
    RESOURCE_EXERCISE: "配套精选习题与实战任务，检验掌握程度。",
}

# 时长(duration, 分钟)与难度(difficulty 1-5)随类型梯度
_TYPE_META: Dict[str, Tuple[int, int]] = {
    RESOURCE_VIDEO: (45, 1),
    RESOURCE_COURSE: (360, 2),
    RESOURCE_ARTICLE: (20, 1),
    RESOURCE_EXERCISE: (90, 3),
}


def seed_learning_resources(db: Session) -> Dict[str, int]:
    """为每个技能/知识点生成 4 条资源（按名称幂等）。"""
    nodes = db.scalars(
        select(SkillNode).where(
            SkillNode.node_type.in_([NODE_SKILL, NODE_KNOWLEDGE])
        )
    ).all()

    existing = {
        r.title
        for r in db.scalars(
            select(LearningResource).where(LearningResource.title.like("【%"))
        ).all()
    }

    created = 0
    for node in nodes:
        for rtype, (title_tpl, _) in _TEMPLATES.items():
            title = title_tpl.format(name=node.name)
            if title in existing:
                continue
            duration, difficulty = _TYPE_META[rtype]
            db.add(
                LearningResource(
                    title=title,
                    type=rtype,
                    url=_demo_url(node, rtype),
                    skill_node_id=node.id,
                    difficulty=difficulty,
                    duration=duration,
                    description=_DESCS[rtype],
                )
            )
            existing.add(title)
            created += 1
    db.commit()
    return {"resources": len(nodes) * len(_TEMPLATES), "created": created}


def _demo_url(node: SkillNode, rtype: str) -> str:
    """演示环境资源链接（离线不可外联，仅作占位）。"""
    ext = {"video": "html5", "course": "lesson", "article": "post", "exercise": "practise"}[rtype]
    return f"https://learn.skillquest.demo/{ext}/{node.id}"