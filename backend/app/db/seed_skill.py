"""
SkillQuest AI 岗位技能图谱种子数据（模块4）

内置技能层级：岗位族 → 岗位 → 能力域 → 技能 → 知识点。
测试与生产复用：seed_skill(db) 幂等写入。

job_skill_relations 直接关联到「技能」层（level2），
required_level / importance 在技能粒度落库，供 Skill Gap 分析。
"""

from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.skill import (
    JOB_ACTIVE,
    Job,
    JobSkillRelation,
    NODE_CAPABILITY,
    NODE_KNOWLEDGE,
    NODE_SKILL,
    SkillNode,
)

# -------------------------------------------------------------------- #
# 节点定义：name -> (importance, description, prerequisites)
# -------------------------------------------------------------------- #
CAPABILITIES: Dict[str, Tuple[int, str]] = {
    "编程基础": (90, "软件开发的核心语言与算法能力"),
    "AI 理论": (90, "机器学习与人工智能基础理论"),
    "工程实践": (85, "将技术落地的工程化能力"),
    "产品与协作": (60, "产品思维与跨团队协作能力"),
    "数据与算法分析": (85, "数据分析与算法应用能力"),
    "视觉与交互": (70, "界面视觉与交互体验设计能力"),
}

SKILLS: Dict[str, Tuple[str, int, str, List[str]]] = {
    # 编程基础
    "Python 基础": ("编程基础", 95, "Python 语法与应用开发", []),
    "JavaScript/TypeScript": ("编程基础", 80, "前端核心语言与工程实践", []),
    "数据结构与算法": ("编程基础", 85, "经典数据结构与算法思维", ["Python 基础"]),
    # AI 理论
    "机器学习基础": ("AI 理论", 95, "机器学习核心概念与建模流程", ["Python 基础", "数据结构与算法"]),
    "深度学习基础": ("AI 理论", 90, "神经网络与深度学习原理", ["机器学习基础"]),
    "提示工程": ("AI 理论", 75, "大模型 Prompt 设计与应用", []),
    # 工程实践
    "Web 全栈开发": ("工程实践", 90, "前后端一体的产品开发能力", ["Python 基础", "JavaScript/TypeScript"]),
    "API 设计与部署": ("工程实践", 80, "接口设计与工程化部署", ["Web 全栈开发"]),
    "数据工程": ("工程实践", 80, "数据获取、加工与建模基础", ["Python 基础"]),
    # 产品与协作
    "产品思维": ("产品与协作", 85, "需求洞察与产品规划能力", []),
    "沟通协作": ("产品与协作", 75, "跨角色沟通与团队协作", []),
    # 数据与算法分析
    "统计分析基础": ("数据与算法分析", 90, "统计学基础与推断分析", ["Python 基础"]),
    "机器学习应用": ("数据与算法分析", 90, "机器学习模型的落地应用", ["机器学习基础", "统计分析基础"]),
    # 视觉与交互
    "视觉设计": ("视觉与交互", 90, "视觉表达与设计系统", []),
    "交互设计": ("视觉与交互", 90, "用户流程与交互体验", ["视觉设计"]),
}

KNOWLEDGE: Dict[str, Tuple[str, List[str]]] = {
    # 编程基础
    "语法与数据类型": ("Python 基础", []),
    "函数与模块": ("Python 基础", []),
    "面向对象": ("Python 基础", ["函数与模块"]),
    "ES 语法": ("JavaScript/TypeScript", []),
    "异步编程": ("JavaScript/TypeScript", ["ES 语法"]),
    "DOM 与浏览器": ("JavaScript/TypeScript", ["ES 语法"]),
    "线性结构": ("数据结构与算法", []),
    "排序与查找": ("数据结构与算法", ["线性结构"]),
    "递归与动态规划": ("数据结构与算法", ["排序与查找"]),
    # AI 理论
    "监督/无监督学习": ("机器学习基础", []),
    "特征工程": ("机器学习基础", []),
    "模型评估": ("机器学习基础", ["特征工程"]),
    "神经网络": ("深度学习基础", ["机器学习基础"]),
    "CNN/RNN": ("深度学习基础", ["神经网络"]),
    "训练与调优": ("深度学习基础", ["CNN/RNN"]),
    "Prompt 设计": ("提示工程", []),
    "RAG 入门": ("提示工程", ["Prompt 设计"]),
    "工具调用": ("提示工程", ["Prompt 设计"]),
    # 工程实践
    "前后端分离": ("Web 全栈开发", []),
    "REST/GraphQL": ("Web 全栈开发", ["前后端分离"]),
    "状态管理": ("Web 全栈开发", ["前后端分离"]),
    "接口规范": ("API 设计与部署", []),
    "容器与 CI/CD": ("API 设计与部署", ["接口规范"]),
    "云上部署": ("API 设计与部署", ["容器与 CI/CD"]),
    "SQL 与取数": ("数据工程", []),
    "ETL 基础": ("数据工程", ["SQL 与取数"]),
    "数据仓库": ("数据工程", ["ETL 基础"]),
    # 产品与协作
    "需求分析": ("产品思维", []),
    "用户研究": ("产品思维", ["需求分析"]),
    "优先级决策": ("产品思维", ["需求分析"]),
    "团队协作": ("沟通协作", []),
    "复盘机制": ("沟通协作", ["团队协作"]),
    "文档表达": ("沟通协作", []),
    # 数据与算法分析
    "描述统计": ("统计分析基础", []),
    "概率分布": ("统计分析基础", ["描述统计"]),
    "假设检验": ("统计分析基础", ["概率分布"]),
    "模型选择": ("机器学习应用", ["机器学习基础"]),
    "效果评估": ("机器学习应用", ["模型选择"]),
    "上线监控": ("机器学习应用", ["效果评估"]),
    # 视觉与交互
    "版式与配色": ("视觉设计", []),
    "设计系统": ("视觉设计", ["版式与配色"]),
    "图标与插画": ("视觉设计", ["版式与配色"]),
    "用户流程": ("交互设计", []),
    "原型制作": ("交互设计", ["用户流程"]),
    "可用性测试": ("交互设计", ["原型制作"]),
}

# -------------------------------------------------------------------- #
# 岗位定义：job -> [(技能名, importance, required_level), ...]
# -------------------------------------------------------------------- #
JOBS: Dict[str, Tuple[str, str, str, List[Tuple[str, int, int]]]] = {
    "AI 应用开发工程师": (
        "技术研发",
        "面向 AI 应用的全栈开发工程师，负责智能应用的前后端与模型集成。",
        "互联网/人工智能",
        [
            ("Python 基础", 95, 80), ("JavaScript/TypeScript", 85, 70),
            ("数据结构与算法", 80, 65), ("机器学习基础", 90, 70),
            ("提示工程", 85, 65), ("深度学习基础", 70, 45),
            ("Web 全栈开发", 95, 75), ("API 设计与部署", 80, 65),
            ("数据工程", 65, 50), ("产品思维", 60, 50), ("沟通协作", 55, 60),
        ],
    ),
    "后端工程师": (
        "技术研发",
        "负责服务端架构、接口与业务逻辑的高可用开发。",
        "互联网/软件",
        [
            ("Python 基础", 90, 75), ("数据结构与算法", 85, 70),
            ("数据工程", 85, 70), ("API 设计与部署", 90, 75),
            ("Web 全栈开发", 70, 55), ("沟通协作", 55, 50),
        ],
    ),
    "数据分析师": (
        "技术研发",
        "通过数据清洗、建模与分析支撑业务决策。",
        "互联网/金融",
        [
            ("数据工程", 90, 75), ("统计分析基础", 95, 80),
            ("机器学习应用", 80, 65), ("Python 基础", 80, 65),
            ("机器学习基础", 60, 45), ("产品思维", 60, 50),
        ],
    ),
    "AI 算法工程师": (
        "技术研发",
        "研究并落地机器学习/深度学习模型。",
        "互联网/人工智能",
        [
            ("Python 基础", 90, 75), ("数据结构与算法", 90, 75),
            ("机器学习基础", 95, 80), ("深度学习基础", 95, 80),
            ("统计分析基础", 85, 70), ("机器学习应用", 90, 75),
            ("提示工程", 70, 55),
        ],
    ),
    "产品经理": (
        "产品设计",
        "洞察需求、规划产品并协调团队交付价值。",
        "互联网/消费",
        [
            ("产品思维", 95, 80), ("沟通协作", 90, 75),
            ("数据工程", 65, 45), ("Web 全栈开发", 40, 25),
            ("机器学习基础", 40, 20),
        ],
    ),
    "UI/UX 设计师": (
        "产品设计",
        "负责产品界面视觉与交互体验设计。",
        "互联网/消费",
        [
            ("视觉设计", 95, 80), ("交互设计", 95, 80),
            ("产品思维", 80, 65), ("Web 全栈开发", 55, 40),
            ("沟通协作", 70, 60),
        ],
    ),
}

CAP_DESCS = CAPABILITIES


def _find(db: Session, model, **kwargs):
    return db.scalar(select(model).where(*[getattr(model, k) == v for k, v in kwargs.items()]))


def seed_skill(db: Session) -> Dict[str, int]:
    """幂等写入技能图谱种子数据。

    Returns:
        {"jobs": 岗位数, "capabilities": 能力域数, "skills": 技能数, "knowledges": 知识点数}
    """
    # ---- 1) 能力域 ----
    cap_by_name: Dict[str, SkillNode] = {}
    for name, (importance, desc) in CAP_DESCS.items():
        exist = _find(db, SkillNode, name=name, node_type=NODE_CAPABILITY)
        node = exist or SkillNode(
            name=name,
            node_type=NODE_CAPABILITY,
            level=1,
            importance=importance,
            description=desc,
            prerequisites_json=[],
        )
        db.add(node)
        cap_by_name[name] = node
    db.flush()

    # ---- 2) 技能（挂在能力域下） ----
    skill_by_name: Dict[str, SkillNode] = {}
    for name, (cap, importance, desc, prereqs) in SKILLS.items():
        exist = _find(db, SkillNode, name=name, node_type=NODE_SKILL)
        node = exist or SkillNode(
            name=name,
            node_type=NODE_SKILL,
            level=2,
            parent_id=cap_by_name[cap].id,
            importance=importance,
            description=desc,
            prerequisites_json=prereqs,
        )
        db.add(node)
        skill_by_name[name] = node
    db.flush()

    # ---- 3) 知识点（挂在技能下） ----
    for name, (skill, prereqs) in KNOWLEDGE.items():
        exist = _find(db, SkillNode, name=name, node_type=NODE_KNOWLEDGE)
        node = exist or SkillNode(
            name=name,
            node_type=NODE_KNOWLEDGE,
            level=3,
            parent_id=skill_by_name[skill].id,
            importance=60,
            description="知识点：{}".format(name),
            prerequisites_json=prereqs,
        )
        db.add(node)
    db.flush()

    # ---- 4) 岗位 + 岗位技能关系 ----
    job_map: Dict[str, Job] = {}
    for job_name, (family, desc, industry, rels) in JOBS.items():
        job = _find(db, Job, job_name=job_name)
        if job is None:
            job = Job(
                job_name=job_name,
                job_family=family,
                description=desc,
                industry=industry,
                status=JOB_ACTIVE,
            )
            db.add(job)
            db.flush()
        job_map[job_name] = job

        existing_rels = {
            r.skill_node_id
            for r in db.scalars(
                select(JobSkillRelation).where(JobSkillRelation.job_id == job.id)
            ).all()
        }
        for skill_name, importance, required in rels:
            skill = skill_by_name.get(skill_name)
            if skill is None or skill.id in existing_rels:
                continue
            db.add(
                JobSkillRelation(
                    job_id=job.id,
                    skill_node_id=skill.id,
                    importance=importance,
                    required_level=required,
                )
            )
    db.flush()

    return {
        "jobs": len(job_map),
        "capabilities": len(cap_by_name),
        "skills": len(skill_by_name),
        "knowledges": len(KNOWLEDGE),
    }