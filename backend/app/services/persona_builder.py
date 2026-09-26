"""
SkillQuest AI 用户画像构建服务（模块3）

规则优先：画像标签、雷达图、兴趣/价值观解析全部规则计算；
Career Agent（大模型）仅对综述/优势/短板做解释性增强，未配置 LLM 时自动降级为规则模板。
"""

import re
from typing import Any, Dict, List, Optional

from app.services.agent_service import AgentInput, agent_service
from app.services.assessment_scoring import (
    ABILITY_DIMENSIONS,
    DIMENSION_LABELS,
    build_radar_data,
)
from app.services.career_recommender import CAREER_DEFS, resolve_target_job


# -------------------------------------------------------------------- #
# 规则标签生成
# -------------------------------------------------------------------- #
def build_persona_tags(
    dimension_scores: Dict[str, float], interest_data: Optional[Dict[str, Any]]
) -> List[str]:
    """按得分阈值生成画像标签（规则）。"""
    tags: List[str] = []

    ability_labels = {
        "logic": ["逻辑缜密型", "逻辑基础型"],
        "programming": ["编程潜力股", "编程入门期"],
        "data": ["数据敏感型", "数据感知起步"],
        "spatial": ["空间感知强", "空间感一般"],
        "language": ["表达沟通型", "表达待打磨"],
        "hands_on": ["动手实践型", "动手待加强"],
    }
    for dim in ABILITY_DIMENSIONS:
        score = dimension_scores.get(dim, 0.0)
        label_list = ability_labels.get(dim, [])
        if score >= 70:
            tags.append(label_list[0])
        elif 40 <= score < 70:
            tags.append(label_list[1])

    if interest_data:
        for item in interest_data.get("interest", []):
            picked = item.get("answer", [])
            labels = [
                p.get("label", "")
                for p in picked
                if isinstance(p, dict) and p.get("label")
            ]
            if labels:
                tags.append("兴趣：" + "、".join(labels[:3]))

    return tags[:8] if tags else ["画像待完善"]


def _pick_top_job(recommended_jobs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not recommended_jobs:
        return None
    return max(recommended_jobs, key=lambda x: x.get("match_score", 0))


# -------------------------------------------------------------------- #
# 画像核心载荷（规则构建，无 AI）
# -------------------------------------------------------------------- #
def build_persona_payload(
    dimension_scores: Dict[str, float],
    interest_data: Optional[Dict[str, Any]],
    values_data: Optional[Dict[str, Any]],
    recomm_result: Dict[str, Any],
    learning_goal: Optional[str],
    job_intention: Optional[str],
) -> Dict[str, Any]:
    """组装 user_personas 各 JSON 字段（不含 AI 综述增强）。"""
    jobs = recomm_result.get("jobs", [])
    top_job = _pick_top_job(jobs)
    tags = build_persona_tags(dimension_scores, interest_data)

    radar = build_radar_data(dimension_scores)

    # target_job：优先用户显式职业意向（文本命中职业库），其次推荐 Top1
    target_job = resolve_target_job(job_intention, (top_job or {}).get("job_name"))

    # learning_goal 兜底：规则模板
    effective_goal = (learning_goal or "").strip() or None
    if not effective_goal and top_job:
        effective_goal = "围绕目标岗位「{}」补齐核心技能差距，并完成阶段性实战项目。".format(
            top_job["job_name"]
        )

    return {
        "persona_tags_json": {
            "tags": tags,
            "summary": "",
            "strengths": [],
            "weaknesses": [],
            "advice": "",
            "ai_enriched": False,
        },
        "ability_radar_json": radar,
        "interest_json": interest_data or {},
        "values_json": values_data or {},
        "learning_goal": effective_goal,
        "target_job": target_job,
    }


# -------------------------------------------------------------------- #
# Career Agent 增强（可选）：综述 / 优势 / 短板 / 建议
# -------------------------------------------------------------------- #
def _fallback_tagged(dimension_scores: Dict[str, float], recomm_result: Dict[str, Any]) -> Dict[str, Any]:
    """无 LLM 时的规则版画像综述（仍保证字段齐全）。"""
    jobs = recomm_result.get("jobs", [])
    top_job = _pick_top_job(jobs) or {}

    ordered = ["logic", "programming", "data", "spatial", "language", "hands_on"]
    strong = [
        DIMENSION_LABELS[d] for d in ordered
        if d in dimension_scores and dimension_scores[d] >= 70
    ]
    weak = [
        DIMENSION_LABELS[d] for d in ordered
        if d in dimension_scores and dimension_scores[d] < 55
    ]

    strengths = [
        "{}({}分)".format(label, int(dimension_scores[label_key]))
        for label, label_key in [("逻辑", "logic"), ("编程", "programming"),
                                 ("数据", "data"), ("空间", "spatial"),
                                 ("语言", "language"), ("动手", "hands_on")]
        if dimension_scores.get(label_key, 0) >= 70
    ] or ["无明显突出强项"]

    weaknesses = [
        "{}({}分)待提升".format(label, int(dimension_scores[label_key]))
        for label, label_key in [("逻辑", "logic"), ("编程", "programming"),
                                 ("数据", "data"), ("空间", "spatial"),
                                 ("语言", "language"), ("动手", "hands_on")]
        if dimension_scores.get(label_key, 0) < 55
    ] or ["暂无明确短板"]

    strong_txt = "、".join(strong) if strong else "暂无显著强项"
    weak_txt = ("短板维度为" + "、".join(weak) + "，") if weak else ""
    summary = "综合测评显示，你的突出能力集中在{}。{}建议围绕「{}」制定学习计划并补齐技能差距。".format(
        strong_txt, weak_txt, top_job.get("job_name") or "目标岗位"
    )
    advice = (
        "保持优势维度的持续投入；针对短板制定专项训练；定期复盘学习记录并重新测评检验进步。"
    )
    return {"summary": summary, "strengths": strengths, "weaknesses": weaknesses, "advice": advice}


async def enhance_persona_with_career_agent(
    payload: Dict[str, Any],
    dimension_scores: Dict[str, float],
    recomm_result: Dict[str, Any],
    raw_answers_summary: str,
) -> Dict[str, Any]:
    """调用 Career Agent（统一 AgentService）生成画像综述；失败/未配置降级为规则模板。"""
    fallback = _fallback_tagged(dimension_scores, recomm_result)
    jobs = recomm_result.get("jobs", [])
    top_job = _pick_top_job(jobs) or {}

    result = await agent_service.run(
        AgentInput(
            agent_type="career",
            user_context={
                "target_job": payload.get("target_job") or top_job.get("job_name"),
                "dimension_scores": {
                    DIMENSION_LABELS.get(d, d): int(v)
                    for d, v in sorted(
                        dimension_scores.items(), key=lambda x: x[1], reverse=True
                    )
                    if d in DIMENSION_LABELS
                },
                "recommended_jobs": [
                    {
                        "job_name": j.get("job_name"),
                        "job_family": j.get("job_family") or "",
                        "match_score": j.get("match_score"),
                        "reason": j.get("reason") or "",
                    }
                    for j in jobs[:3]
                ],
                "raw_answers_summary": raw_answers_summary[:800],
            },
            fallback=fallback,
            max_tokens=1024,
        )
    )

    if result.degraded or not result.ok or not result.data:
        # 未配置模型 / 调用失败：规则模板兜底（不标记 ai_enriched）
        payload["persona_tags_json"].update(result.data if result.data else fallback)
        return payload

    data = result.data
    tags = (payload["persona_tags_json"].get("tags") or []) + (
        data.get("persona_tags") or []
    )
    payload["persona_tags_json"] = {
        "tags": tags[:12],
        "summary": str(data.get("persona_summary") or fallback["summary"]),
        "strengths": data.get("strengths") or fallback["strengths"],
        "weaknesses": data.get("weaknesses") or fallback["weaknesses"],
        "advice": str(data.get("advice") or fallback["advice"]),
        "ai_enriched": True,
    }
    return payload


# -------------------------------------------------------------------- #
# 简答汇总（供 AI 增强参考）
# -------------------------------------------------------------------- #
def summarize_text_answers(texts: List[str]) -> str:
    return " ".join((t or "").strip() for t in texts)[:300]