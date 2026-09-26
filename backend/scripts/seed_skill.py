#!/usr/bin/env python3
"""
SkillQuest AI 岗位技能图谱种子脚本

用法：
    PYTHONPATH=. python scripts/seed_skill.py
    PYTHONPATH=. python scripts/seed_skill.py --reset   # 删除全部岗位/技能后重建
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete

from app.db.seed_skill import seed_skill
from app.db.session import SessionLocal
from app.models.skill import Job, JobSkillRelation, SkillNode, UserSkillStatus


def main() -> int:
    parser = argparse.ArgumentParser(description="种子：写入岗位技能图谱")
    parser.add_argument("--reset", action="store_true", help="先清空技能相关表再重建")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.reset:
            db.execute(delete(UserSkillStatus))
            db.execute(delete(JobSkillRelation))
            db.execute(delete(SkillNode))
            db.execute(delete(Job))
            db.commit()
            print("已清空旧技能图谱数据")

        result = seed_skill(db)
        db.commit()
        print("技能图谱种子已就绪:")
        for key, value in result.items():
            print("  {}: {}".format(key, value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())