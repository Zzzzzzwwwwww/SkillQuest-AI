"""
SkillQuest AI 阶段测评种子数据（模块7）

为演示环境写入 2 套阶段试卷（bronze / silver），题目关联技能图谱知识点
(skill_nodes.node_type=knowledge)，供「开始测评 → 提交 → 结果复盘」全流程演示。

幂等：按试卷标题判重。
"""

from typing import Any, Dict, List, Tuple

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.assessment_review import (
    EXAM_ACTIVE,
    ExamQuestion,
    QT_JUDGE,
    QT_MULTIPLE,
    QT_SINGLE,
    StageExam,
)
from app.models.skill import NODE_KNOWLEDGE, SkillNode

# 试卷定义：title -> (stage, description, duration, questions)
# question: (question_type, content, options, answer, score, knowledge_point_name)
_EXAMS: Dict[str, Tuple[str, str, int, List[Tuple[str, str, list, Any, int, str]]]] = {
    "青铜试炼 · 编程与 AI 入门": (
        "bronze",
        "入门综合测评：覆盖编程基础、数据结构与算法、机器学习入门三大主题，检验自学基础。",
        30,
        [
            (
                QT_SINGLE,
                "Python 中用于定义列表（List）的符号是？",
                [
                    {"key": "A", "label": "中括号 []"},
                    {"key": "B", "label": "花括号 {}"},
                    {"key": "C", "label": "小括号 ()"},
                    {"key": "D", "label": "尖括号 <>"},
                ],
                "A",
                20,
                "语法与数据类型",
            ),
            (
                QT_JUDGE,
                "Python 中的字典（dict）属于有序的可迭代数据结构。",
                [{"key": "对", "label": "对"}, {"key": "错", "label": "错"}],
                False,
                20,
                "语法与数据类型",
            ),
            (
                QT_MULTIPLE,
                "下列属于算法中常见时间复杂度量级的有？（多选）",
                [
                    {"key": "A", "label": "O(1) 常数级"},
                    {"key": "B", "label": "O(n) 线性级"},
                    {"key": "C", "label": "O(n²) 平方级"},
                    {"key": "D", "label": "O(睡觉) 玄学级"},
                ],
                ["A", "B", "C"],
                20,
                "线性结构",
            ),
            (
                QT_SINGLE,
                "二分查找的前提条件是数据已按什么序排列？",
                [
                    {"key": "A", "label": "乱序"},
                    {"key": "B", "label": "升序/降序"},
                    {"key": "C", "label": "倒序即可"},
                    {"key": "D", "label": "不需要排序"},
                ],
                "B",
                20,
                "排序与查找",
            ),
            (
                QT_SINGLE,
                "监督学习（Supervised Learning）的核心特征是？",
                [
                    {"key": "A", "label": "数据带标签"},
                    {"key": "B", "label": "数据无标签"},
                    {"key": "C", "label": "无需训练"},
                    {"key": "D", "label": "仅用于聚类"},
                ],
                "A",
                20,
                "监督/无监督学习",
            ),
        ],
    ),
    "白银试炼 · AI 应用进阶": (
        "silver",
        "进阶综合测评：覆盖提示工程、机器学习应用与全栈工程实践，检验 AI 应用落地能力。",
        45,
        [
            (
                QT_SINGLE,
                "在 Prompt 设计中，「零样本（Zero-shot）」指什么？",
                [
                    {"key": "A", "label": "不提供任何示例直接提问"},
                    {"key": "B", "label": "提供多个示例再提问"},
                    {"key": "C", "label": "让模型联网检索"},
                    {"key": "D", "label": "关闭模型随机性"},
                ],
                "A",
                20,
                "Prompt 设计",
            ),
            (
                QT_MULTIPLE,
                "RAG（检索增强生成）通常包含哪些核心环节？（多选）",
                [
                    {"key": "A", "label": "文档切分与向量化"},
                    {"key": "B", "label": "相似度检索"},
                    {"key": "C", "label": "上下文拼接生成"},
                    {"key": "D", "label": "模型权重微调"},
                ],
                ["A", "B", "C"],
                20,
                "RAG 入门",
            ),
            (
                QT_JUDGE,
                "特征工程（Feature Engineering）的有无对模型效果没有影响。",
                [{"key": "对", "label": "对"}, {"key": "错", "label": "错"}],
                False,
                20,
                "特征工程",
            ),
            (
                QT_SINGLE,
                "前后端分离架构中，前端通常通过什么与后端交互数据？",
                [
                    {"key": "A", "label": "HTTP/REST 接口"},
                    {"key": "B", "label": "直接读数据库"},
                    {"key": "C", "label": "修改服务器配置文件"},
                    {"key": "D", "label": "共享内存变量"},
                ],
                "A",
                20,
                "前后端分离",
            ),
            (
                QT_SINGLE,
                "防抖（Debounce）与节流（Throttle）主要用于解决哪类问题？",
                [
                    {"key": "A", "label": "高频事件触发导致的性能开销"},
                    {"key": "B", "label": "数据库锁冲突"},
                    {"key": "C", "label": "网络 DNS 解析"},
                    {"key": "D", "label": "图片压缩"},
                ],
                "A",
                20,
                "异步编程",
            ),
        ],
    ),
}


def _kp_id(db: Session, kp_name: str) -> int | None:
    node = db.scalar(
        select(SkillNode).where(
            SkillNode.node_type == NODE_KNOWLEDGE,
            SkillNode.name == kp_name,
        )
    )
    return node.id if node is not None else None


def seed_exams(db: Session) -> Dict[str, int]:
    """写入阶段测评试卷（按标题幂等）。

    Returns:
        {"exams": 试卷数, "questions": 题目数, "created_exams": 新建试卷数}
    """
    total_questions = 0
    created_exams = 0
    for title, (stage, desc, duration, questions) in _EXAMS.items():
        exam = db.scalar(select(StageExam).where(StageExam.title == title))
        if exam is None:
            total = sum(q[4] for q in questions)
            exam = StageExam(
                title=title,
                stage=stage,
                description=desc,
                total_score=total,
                duration=duration,
                status=EXAM_ACTIVE,
            )
            db.add(exam)
            db.flush()
            created_exams += 1
        else:
            existing = db.scalar(
                select(ExamQuestion).where(ExamQuestion.exam_id == exam.id)
            )
            if existing is not None:
                continue
            db.execute(delete(ExamQuestion).where(ExamQuestion.exam_id == exam.id))

        for qtype, content, options, answer, score, kp_name in questions:
            db.add(
                ExamQuestion(
                    exam_id=exam.id,
                    question_type=qtype,
                    content=content,
                    options_json=options,
                    answer=answer,
                    score=score,
                    knowledge_point_id=_kp_id(db, kp_name),
                )
            )
            total_questions += 1
    db.flush()
    return {
        "exams": len(_EXAMS),
        "questions": total_questions,
        "created_exams": created_exams,
    }