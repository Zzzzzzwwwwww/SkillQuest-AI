"""
SkillQuest AI 测评试卷种子数据（模块3）

内置一套"职业发展综合测评 V1"，12 题覆盖 10 个测评维度：
  逻辑/编程/数据/空间/语言/动手/兴趣/职业价值观/学习目标/职业意向，
题型含单选、多选、量表、简答。

测试与生产均可复用：seed_assessment(db, papers) 幂等写入。
"""

from typing import Iterable, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.assessment import (
    AssessmentPaper,
    AssessmentQuestion,
    PAPER_ACTIVE,
)

PAPER_TITLE = "职业发展综合测评 V1"
PAPER_TYPE = "career"


def _q(
    order_no: int,
    qtype: str,
    content: str,
    dimension: str,
    score_rule: dict,
    options: dict | None = None,
) -> AssessmentQuestion:
    return AssessmentQuestion(
        question_type=qtype,
        content=content,
        dimension=dimension,
        score_rule=score_rule,
        options_json=options,
        order_no=order_no,
    )


def build_default_questions() -> List[AssessmentQuestion]:
    """构造默认 12 题（覆盖全部 10 个维度）。"""
    return [
        # 1. 逻辑（单选）
        _q(
            1,
            "single",
            "观察数列：1, 4, 9, 16, ( ? )。括号里应该是多少？",
            "logic",
            {"type": "direct", "values": {"A": 60, "B": 40, "C": 100, "D": 20}},
            {"A": "20", "B": "24", "C": "25", "D": "30"},
        ),
        # 2. 编程（量表）
        _q(
            2,
            "scale",
            "你目前的编程熟练程度是？",
            "programming",
            {"type": "scale", "min": 1, "max": 5, "step": 1},
            {
                "1": "完全零基础",
                "2": "会基础语法",
                "3": "能独立写小脚本",
                "4": "可完成项目开发",
                "5": "具备工程级经验",
            },
        ),
        # 3. 数据（量表）
        _q(
            3,
            "scale",
            "你对数据分析与用数据做决策的熟悉程度是？",
            "data",
            {"type": "scale", "min": 1, "max": 5, "step": 1},
            {
                "1": "非常陌生",
                "2": "接触较少",
                "3": "会做简单统计",
                "4": "常用数据辅助决策",
                "5": "能专业处理数据",
            },
        ),
        # 4. 空间（量表）
        _q(
            4,
            "scale",
            "你在脑中想象物体结构、空间关系或抽象图形的能力如何？",
            "spatial",
            {"type": "scale", "min": 1, "max": 5, "step": 1},
            {"1": "很难想象", "2": "较弱", "3": "一般", "4": "较强", "5": "非常擅长"},
        ),
        # 5. 语言（单选）
        _q(
            5,
            "single",
            "向他人介绍一个复杂想法时，你最常用的方式是？",
            "language",
            {"type": "direct", "values": {"A": 60, "B": 40, "C": 100, "D": 80}},
            {
                "A": "画图/示意图辅助",
                "B": "先动手做出来给对方看",
                "C": "用清晰的逻辑口头讲清楚",
                "D": "整理成文档让对方阅读",
            },
        ),
        # 6. 动手（量表）
        _q(
            6,
            "scale",
            "你的动手实操能力（搭建、调试、故障排查等）如何？",
            "hands_on",
            {"type": "scale", "min": 1, "max": 5, "step": 1},
            {
                "1": "很少动手",
                "2": "需要详细指导",
                "3": "按教程可完成",
                "4": "能独立搭建调试",
                "5": "能解决疑难问题",
            },
        ),
        # 7. 兴趣（多选）
        _q(
            7,
            "multiple",
            "以下哪些技术/业务领域会让你感到兴奋？（可多选）",
            "interest",
            {
                "type": "sum",
                "values": {"A": 20, "B": 20, "C": 20, "D": 20, "E": 20, "F": 20},
                "max": 100,
            },
            {
                "A": "Web 前后端开发",
                "B": "人工智能/算法",
                "C": "数据分析与可视化",
                "D": "产品与商业",
                "E": "设计与创意",
                "F": "云服务/运维/安全",
            },
        ),
        # 8. 兴趣（单选，工作方式偏好）
        _q(
            8,
            "single",
            "你更喜欢哪种工作方式？",
            "interest",
            {"type": "direct", "values": {"A": 90, "B": 70, "C": 60, "D": 50}},
            {
                "A": "独立钻研技术难题",
                "B": "团队协作推进目标",
                "C": "直接面对用户与客户",
                "D": "观察趋势、做前瞻决策",
            },
        ),
        # 9. 职业价值观（多选）
        _q(
            9,
            "multiple",
            "工作中你最看重哪些价值？（最多选 3 项）",
            "work_values",
            {
                "type": "sum",
                "values": {"A": 20, "B": 20, "C": 20, "D": 20, "E": 20, "F": 20},
                "max": 100,
            },
            {
                "A": "高薪回报",
                "B": "持续成长",
                "C": "稳定少变",
                "D": "创造影响力",
                "E": "工作生活平衡",
                "F": "良好团队氛围",
            },
        ),
        # 10. 职业意向（简答）
        _q(
            10,
            "text",
            "你理想中的职业/岗位是什么？选择它的主要原因是什么？",
            "career_intent",
            {
                "type": "text",
                "keywords": [],
                "min_len": 10,
                "max_len": 200,
                "base": 40,
                "placeholder": "例如：希望成为后端工程师，因为喜欢解决复杂业务问题……",
            },
        ),
        # 11. 学习目标（简答）
        _q(
            11,
            "text",
            "你希望通过 SkillQuest 达到什么样的学习目标？",
            "learning_goal",
            {
                "type": "text",
                "keywords": ["算法", "编程", "数据", "产品", "设计", "测试", "运维", "AI", "前端", "后端"],
                "min_len": 10,
                "max_len": 200,
                "base": 40,
                "placeholder": "例如：三个月内掌握 Python 数据分析并完成一个实战项目……",
            },
        ),
        # 12. 编程（单选，补充深度）
        _q(
            12,
            "single",
            "编程中“数组”最贴切的比喻是？",
            "programming",
            {"type": "direct", "values": {"A": 100, "B": 60, "C": 80, "D": 40}},
            {
                "A": "一排编好号的储物柜",
                "B": "一张导航地图",
                "C": "一个能生成物品的清单",
                "D": "一份调味配方",
            },
        ),
    ]


def seed_assessment(
    db: Session,
    title: str = PAPER_TITLE,
    questions: Iterable[AssessmentQuestion] | None = None,
) -> AssessmentPaper:
    """幂等写入试卷：标题已存在则跳过，否则创建试卷并写入题目。

    Returns:
        已存在或新建的试卷对象（已 flush，含 id）。
    """
    exist = db.scalar(select(AssessmentPaper).where(AssessmentPaper.title == title))
    if exist is not None:
        return exist

    paper = AssessmentPaper(
        title=title,
        description="通过 10 个维度综合评估你的能力结构、职业兴趣与价值观，给出 Top3 职业方向与技能差距。",
        type=PAPER_TYPE,
        status=PAPER_ACTIVE,
    )
    db.add(paper)
    db.flush()

    for item in questions or build_default_questions():
        item.paper_id = paper.id
        db.add(item)
    db.flush()
    return paper


def count_questions(db: Session, title: str = PAPER_TITLE) -> int:
    """查询某试卷的题目数量。"""
    paper = db.scalar(select(AssessmentPaper).where(AssessmentPaper.title == title))
    if paper is None:
        return 0
    return int(
        db.scalar(
            select(func.count(AssessmentQuestion.id)).where(
                AssessmentQuestion.paper_id == paper.id
            )
        )
        or 0
    )