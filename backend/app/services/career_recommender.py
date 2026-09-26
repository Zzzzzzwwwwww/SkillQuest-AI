"""
SkillQuest AI 职业推荐规则引擎（模块3）

设计原则（第1条）：匹配度、排序、技能差距全部规则计算；
第3条：Career Agent（大模型）只负责对结果做解释性增强（在 persona_builder 中），
      推荐本身不依赖大模型，未配置 LLM 时仍可完整输出 Top3 推荐。
"""

from typing import Any, Dict, List, Optional

from app.services.assessment_scoring import DIMENSION_LABELS

# -------------------------------------------------------------------- #
# 职业库：权重(维度→重要度) + 必备技能(技能与所在维度门槛分) + 概述
# -------------------------------------------------------------------- #
CAREER_DEFS: List[Dict[str, Any]] = [
    {
        "job_id": "frontend_engineer",
        "job_name": "前端工程师",
        "summary": "构建用户界面、交互与前端工程化",
        "weights": {
            "programming": 0.30, "logic": 0.20, "spatial": 0.16,
            "hands_on": 0.12, "language": 0.10, "data": 0.05,
            "interest": 0.05, "work_values": 0.02,
        },
        "skills": [
            {"skill": "HTML/CSS/JavaScript", "dimension": "programming", "threshold": 60},
            {"skill": "前端框架（React/Vue）", "dimension": "programming", "threshold": 72},
            {"skill": "页面布局与视觉还原", "dimension": "spatial", "threshold": 58},
            {"skill": "联调与问题定位", "dimension": "hands_on", "threshold": 55},
            {"skill": "沟通与需求理解", "dimension": "language", "threshold": 50},
        ],
    },
    {
        "job_id": "backend_engineer",
        "job_name": "后端工程师",
        "summary": "服务端架构、接口与业务逻辑开发",
        "weights": {
            "programming": 0.32, "logic": 0.22, "data": 0.14,
            "hands_on": 0.10, "language": 0.08, "spatial": 0.04,
            "interest": 0.06, "work_values": 0.04,
        },
        "skills": [
            {"skill": "一门后端语言（Python/Java/Go）", "dimension": "programming", "threshold": 65},
            {"skill": "数据库设计与 SQL", "dimension": "data", "threshold": 60},
            {"skill": "接口设计与调试", "dimension": "logic", "threshold": 62},
            {"skill": "部署与排查问题", "dimension": "hands_on", "threshold": 55},
        ],
    },
    {
        "job_id": "algorithm_engineer",
        "job_name": "AI/算法工程师",
        "summary": "机器学习模型研发、调优与落地",
        "weights": {
            "logic": 0.30, "programming": 0.28, "data": 0.22,
            "spatial": 0.06, "language": 0.06, "hands_on": 0.04,
            "interest": 0.04,
        },
        "skills": [
            {"skill": "Python 与科学计算", "dimension": "programming", "threshold": 70},
            {"skill": "线性代数/概率统计", "dimension": "logic", "threshold": 70},
            {"skill": "数据处理与分析", "dimension": "data", "threshold": 72},
            {"skill": "算法实现与实验", "dimension": "hands_on", "threshold": 58},
        ],
    },
    {
        "job_id": "data_analyst",
        "job_name": "数据分析师",
        "summary": "数据清洗、指标建模与业务洞察",
        "weights": {
            "data": 0.34, "logic": 0.24, "programming": 0.16,
            "language": 0.10, "hands_on": 0.06, "spatial": 0.04,
            "interest": 0.04, "work_values": 0.02,
        },
        "skills": [
            {"skill": "SQL 与取数", "dimension": "data", "threshold": 68},
            {"skill": "统计与业务分析", "dimension": "logic", "threshold": 65},
            {"skill": "Python/Pandas 处理", "dimension": "programming", "threshold": 60},
            {"skill": "结论表达与汇报", "dimension": "language", "threshold": 58},
        ],
    },
    {
        "job_id": "product_manager",
        "job_name": "产品经理",
        "summary": "需求洞察、产品规划与跨团队协作",
        "weights": {
            "language": 0.24, "interest": 0.22, "work_values": 0.16,
            "logic": 0.18, "data": 0.10, "spatial": 0.06,
            "hands_on": 0.04,
        },
        "skills": [
            {"skill": "需求沟通与表达", "dimension": "language", "threshold": 65},
            {"skill": "用户与市场洞察", "dimension": "interest", "threshold": 62},
            {"skill": "结构化思考", "dimension": "logic", "threshold": 60},
            {"skill": "数据驱动决策", "dimension": "data", "threshold": 55},
        ],
    },
    {
        "job_id": "ux_designer",
        "job_name": "UI/UX 设计师",
        "summary": "界面视觉、交互体验与设计系统",
        "weights": {
            "spatial": 0.32, "hands_on": 0.20, "interest": 0.18,
            "programming": 0.10, "language": 0.10, "logic": 0.06,
            "work_values": 0.04,
        },
        "skills": [
            {"skill": "设计工具与视觉表达", "dimension": "spatial", "threshold": 68},
            {"skill": "原型与交互设计", "dimension": "hands_on", "threshold": 60},
            {"skill": "审美与创意感知", "dimension": "interest", "threshold": 60},
            {"skill": "设计稿到代码还原", "dimension": "programming", "threshold": 45},
        ],
    },
    {
        "job_id": "qa_engineer",
        "job_name": "测试工程师",
        "summary": "质量保障、自动化测试与缺陷分析",
        "weights": {
            "logic": 0.26, "programming": 0.22, "data": 0.14,
            "hands_on": 0.14, "language": 0.10, "spatial": 0.06,
            "interest": 0.04, "work_values": 0.04,
        },
        "skills": [
            {"skill": "用例设计与边界思维", "dimension": "logic", "threshold": 62},
            {"skill": "自动化测试脚本", "dimension": "programming", "threshold": 55},
            {"skill": "缺陷定位与复现", "dimension": "hands_on", "threshold": 58},
        ],
    },
    {
        "job_id": "devops_engineer",
        "job_name": "运维/DevOps 工程师",
        "summary": "CI/CD、容器化与系统稳定性保障",
        "weights": {
            "programming": 0.26, "hands_on": 0.22, "logic": 0.18,
            "data": 0.14, "language": 0.08, "spatial": 0.06,
            "interest": 0.04, "work_values": 0.02,
        },
        "skills": [
            {"skill": "脚本/自动化（Shell/Python）", "dimension": "programming", "threshold": 62},
            {"skill": "系统排查与运维实操", "dimension": "hands_on", "threshold": 65},
            {"skill": "日志与监控分析", "dimension": "data", "threshold": 55},
        ],
    },
]


# -------------------------------------------------------------------- #
# 规则推荐主流程
# -------------------------------------------------------------------- #
def recommend_jobs(dimension_scores: Dict[str, float], top_n: int = 3) -> Dict[str, Any]:
    """基于维度得分（0-100）规则计算 TopN 职业推荐。

    Returns:
        {
          "source": "rule",
          "jobs": [ {job_id, job_name, summary, match_score, reason, skill_gaps:[...]} ]
        }
    """
    scored: List[Dict[str, Any]] = []
    for career in CAREER_DEFS:
        weights = career["weights"]
        total_w = sum(weights.values())
        if total_w <= 0:
            continue
        match = sum(
            weights.get(dim, 0.0) * dimension_scores.get(dim, 0.0)
            for dim in weights
        ) / total_w
        match = round(max(0.0, min(100.0, match)), 1)

        reason = build_reason(career, dimension_scores)
        gaps = compute_skill_gaps(career, dimension_scores)

        scored.append(
            {
                "job_id": career["job_id"],
                "job_name": career["job_name"],
                "summary": career["summary"],
                "match_score": match,
                "reason": reason,
                "skill_gaps": gaps,
            }
        )

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return {"source": "rule", "jobs": scored[:top_n]}


def build_reason(career: Dict[str, Any], scores: Dict[str, float]) -> str:
    """规则生成推荐理由：突出用户得分最高的维度与岗位要求契合点。"""
    weights = career["weights"]
    ranked = sorted(
        ((dim, scores.get(dim, 0.0)) for dim in weights if dim in scores),
        key=lambda x: x[1],
        reverse=True,
    )
    top_three = [DIMENSION_LABELS[d] for d, _ in ranked[:3] if d in DIMENSION_LABELS]
    if not top_three:
        return "你的核心能力结构与该岗位的通用要求较为匹配。"
    return "你的核心优势（{}）与{}所需的关键能力高度契合。".format(
        "、".join(top_three), career["job_name"]
    )


def compute_skill_gaps(
    career: Dict[str, Any], scores: Dict[str, float]
) -> List[Dict[str, Any]]:
    """计算岗位必备技能差距：current=维度得分, threshold=门槛分, gap 为差值。"""
    gaps: List[Dict[str, Any]] = []
    for skill in career.get("skills", []):
        dim = skill["dimension"]
        threshold = float(skill["threshold"])
        current = scores.get(dim, 0.0)
        gap = round(max(0.0, threshold - current), 1)
        gaps.append(
            {
                "skill": skill["skill"],
                "dimension": dim,
                "current": current,
                "threshold": threshold,
                "gap": gap,
            }
        )
    # 已达标项放在最后（前端可折叠展示差距列表）
    gaps.sort(key=lambda x: x["gap"], reverse=True)
    return gaps


def resolve_target_job(
    job_intention: Optional[str], top_job_name: Optional[str]
) -> Optional[str]:
    """确定画像中的目标岗位：意向文本命中职业库名称则采纳，否则用推荐 Top1。

    Args:
        job_intention: 用户在测评/画像中填写的职业意向（原始文本）。
        top_job_name: 规则推荐 Top1 岗位名。
    """
    if job_intention and job_intention.strip():
        text = job_intention.strip()
        for career in CAREER_DEFS:
            if career["job_name"] in text:
                return career["job_name"]
    return top_job_name