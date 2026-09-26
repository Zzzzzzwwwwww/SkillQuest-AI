#!/usr/bin/env python3
"""
SkillQuest AI 测评试卷种子脚本

用法：
    PYTHONPATH=. python scripts/seed_assessment.py
    PYTHONPATH=. python scripts/seed_assessment.py --reset   # 删除同名试卷后重建

依赖：启动脚本前请先执行 alembic upgrade head。
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select

from app.db.seed_assessment import (
    PAPER_TITLE,
    build_default_questions,
    seed_assessment,
)
from app.db.session import SessionLocal
from app.models.assessment import AssessmentPaper, AssessmentQuestion


def main() -> int:
    parser = argparse.ArgumentParser(description="种子：写入职业测评试卷")
    parser.add_argument("--reset", action="store_true", help="先删除同名试卷再重建")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.reset:
            paper = db.scalar(
                select(AssessmentPaper).where(AssessmentPaper.title == PAPER_TITLE)
            )
            if paper is not None:
                db.execute(
                    delete(AssessmentQuestion).where(
                        AssessmentQuestion.paper_id == paper.id
                    )
                )
                db.execute(
                    delete(AssessmentPaper).where(AssessmentPaper.id == paper.id)
                )
                db.commit()
                print("已删除旧试卷:", PAPER_TITLE)

        paper = seed_assessment(db)
        db.commit()
        print("试卷已就绪:")
        print("  id        :", paper.id)
        print("  标题      :", paper.title)
        print("  题目数    :", len(build_default_questions()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())