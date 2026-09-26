"""
SkillQuest AI 测评评分规则引擎（模块3）

设计原则（第1条）：能规则算的不用大模型 ——
  每题得分、维度得分、总分、雷达图数据全部由本模块规则计算，AI 不参与任何算分。

题型与评分规则（question.score_rule）：
  - single   单选：{"type": "direct", "values": {"A": 20, ...}}        → 取选中项分值（0-100）
  - multiple 多选：{"type": "sum", "values": {"A": 10, ...}, "max": 100} → 命中项分值求和并封顶归一
  - scale    量表：{"type": "scale", "min": 1, "max": 5}               → (值-min)/(max-min)*100 线性映射
  - text     简答：{"type": "text", "keywords": [...], "min_len": .., "max_len": ..} → 长度+关键词启发式
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.models.assessment import (
    AssessmentQuestion,
    QUESTION_MULTIPLE,
    QUESTION_SCALE,
    QUESTION_SINGLE,
    QUESTION_TEXT,
)

# -------------------------------------------------------------------- #
# 测评维度定义（10 维）
# -------------------------------------------------------------------- #
DIM_LOGIC = "logic"          # 逻辑
DIM_PROGRAMMING = "programming"  # 编程
DIM_DATA = "data"            # 数据
DIM_SPATIAL = "spatial"      # 空间
DIM_LANGUAGE = "language"    # 语言
DIM_HANDS_ON = "hands_on"    # 动手
DIM_INTEREST = "interest"    # 兴趣
DIM_WORK_VALUES = "work_values"  # 职业价值观
DIM_LEARNING_GOAL = "learning_goal"  # 学习目标
DIM_CAREER_INTENT = "career_intent"  # 职业意向

# 能力六维（能力雷达图 / 技能差距计算使用）
ABILITY_DIMENSIONS: Tuple[str, ...] = (
    DIM_LOGIC,
    DIM_PROGRAMMING,
    DIM_DATA,
    DIM_SPATIAL,
    DIM_LANGUAGE,
    DIM_HANDS_ON,
)

# 偏好四维（兴趣/价值观/目标/意向，参与职业推荐加权）
PREFERENCE_DIMENSIONS: Tuple[str, ...] = (
    DIM_INTEREST,
    DIM_WORK_VALUES,
    DIM_LEARNING_GOAL,
    DIM_CAREER_INTENT,
)

# 维度中文名（前端展示与推荐理由模板共用）
DIMENSION_LABELS: Dict[str, str] = {
    DIM_LOGIC: "逻辑",
    DIM_PROGRAMMING: "编程",
    DIM_DATA: "数据",
    DIM_SPATIAL: "空间",
    DIM_LANGUAGE: "语言",
    DIM_HANDS_ON: "动手",
    DIM_INTEREST: "兴趣",
    DIM_WORK_VALUES: "职业价值观",
    DIM_LEARNING_GOAL: "学习目标",
    DIM_CAREER_INTENT: "职业意向",
}

# 雷达图默认六维（未测维度记 0，保证图形稳定）
RADAR_DIMENSIONS: Tuple[str, ...] = ABILITY_DIMENSIONS


# -------------------------------------------------------------------- #
# 单题评分
# -------------------------------------------------------------------- #
def score_question(
    question: AssessmentQuestion, raw_answer: Any = None
) -> float:
    """按题型与 score_rule 对一题作答评分，返回 0-100 分。

    Args:
        question: 题库中的题目对象
        raw_answer: 客户端提交的答案（字符串 / 列表 / 数字均可），
                    与前端 answer 字段一一对应。
    """
    rule: Dict[str, Any] = question.score_rule or {}
    qtype: str = question.question_type

    if raw_answer is None or raw_answer == "" or raw_answer == []:
        return 0.0

    values: Dict[str, Any] = rule.get("values") or {}

    if qtype == QUESTION_SINGLE:
        return _to_score(values.get(str(raw_answer), 0))

    if qtype == QUESTION_MULTIPLE:
        selected = raw_answer if isinstance(raw_answer, list) else [raw_answer]
        hits = sum(float(values.get(str(k), 0)) for k in selected)
        ceiling = float(rule.get("max", 100) or 100)
        if ceiling <= 0:
            ceiling = 100.0
        return _to_score(min(hits, ceiling))

    if qtype == QUESTION_SCALE:
        lo = float(rule.get("min", 1))
        hi = float(rule.get("max", 5))
        try:
            val = float(raw_answer)
        except (TypeError, ValueError):
            return 0.0
        span = hi - lo
        if span <= 0:
            return _to_score(val)
        return _to_score((val - lo) / span * 100)

    if qtype == QUESTION_TEXT:
        return _score_text(rule, str(raw_answer))

    return 0.0


def _score_text(rule: Dict[str, Any], text: str) -> float:
    """简答题启发式评分：长度达标 + 关键词命中，封顶 100。"""
    content = text.strip()
    if not content:
        return 0.0
    max_len = int(rule.get("max_len", 200) or 200)
    min_len = int(rule.get("min_len", 10) or 10)
    base = float(rule.get("base", 30) or 30)

    score = base
    if min_len > 0:
        score += min((len(content) / min_len) * 20, 20.0)
    keywords: List[str] = rule.get("keywords") or []
    if keywords:
        hits = sum(1 for kw in keywords if kw in content)
        score += hits * 10.0
    return _to_score(min(score, 100.0))


def _to_score(value: float) -> float:
    """归一化到 0-100（四舍五入保留 1 位小数）。"""
    return round(max(0.0, min(100.0, float(value))), 1)


# -------------------------------------------------------------------- #
# 维度聚合 / 总分 / 雷达图
# -------------------------------------------------------------------- #
def aggregate_dimension_scores(
    questions: Sequence[AssessmentQuestion],
    scores: Sequence[float],
) -> Dict[str, float]:
    """按维度聚合得分：维度得分 = 该维度所有题目得分的均值。"""
    buckets: Dict[str, List[float]] = {}
    for q, s in zip(questions, scores):
        buckets.setdefault(q.dimension, []).append(float(s))
    return {
        dim: round(sum(items) / len(items), 1)
        for dim, items in buckets.items()
        if items
    }


def total_score(dimension_scores: Dict[str, float]) -> float:
    """总分 = 所有有得分维度的均值（0-100）。"""
    if not dimension_scores:
        return 0.0
    return round(
        sum(dimension_scores.values()) / len(dimension_scores), 1
    )


def build_radar_data(
    dimension_scores: Dict[str, float],
) -> Dict[str, Any]:
    """生成能力雷达图数据（ECharts 直接渲染）。"""
    return {
        "dimensions": [
            {
                "name": DIMENSION_LABELS[dim],
                "key": dim,
                "score": _to_score(dimension_scores.get(dim, 0)),
            }
            for dim in RADAR_DIMENSIONS
        ]
    }


# -------------------------------------------------------------------- #
# 画像辅助：兴趣 / 价值观解析（从测评答案中提取偏好原始信息）
# -------------------------------------------------------------------- #
def resolve_preference_answers(
    questions: Sequence[AssessmentQuestion],
    answers: Sequence[Any],
    dimensions: Sequence[str],
) -> Dict[str, Any]:
    """从作答中提取指定维度的原始答案（供画像 interest/values 落库）。"""
    result: Dict[str, Any] = {}
    for q, ans in zip(questions, answers):
        if q.dimension not in dimensions:
            continue
        label = q.content[:60]
        options = q.options_json or {}
        if isinstance(ans, list):
            picked = [
                {"key": k, "label": options.get(str(k), str(k))}
                for k in ans
                if k in options
            ]
            result.setdefault(q.dimension, []).append(
                {"question": label, "answer": picked, "raw": ans}
            )
        else:
            result.setdefault(q.dimension, []).append(
                {
                    "question": label,
                    "answer": {
                        "key": str(ans),
                        "label": options.get(str(ans), str(ans)),
                    }
                    if str(ans) in options
                    else str(ans),
                    "raw": ans,
                }
            )
    return result