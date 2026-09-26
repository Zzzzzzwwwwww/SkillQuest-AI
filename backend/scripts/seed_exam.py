#!/usr/bin/env python3
"""独立运行：为阶段测评表写入 2 套演示试卷（青铜/白银）。

用法：
    PYTHONPATH=. python scripts/seed_exam.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import warnings

warnings.filterwarnings("ignore")

import app.db.session as ds
from app.db.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DEMO_DB = Path(__file__).resolve().parents[1] / "sq_demo.db"


def main() -> int:
    engine = create_engine(f"sqlite:///{DEMO_DB}", connect_args={"check_same_thread": False})
    ds.engine = engine
    ds.SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    ds.check_db_health = lambda: {"connected": True}
    ds.check_redis_health = lambda: {"connected": True}

    Base.metadata.create_all(engine)

    from app.db.seed_exam import seed_exams

    with ds.SessionLocal() as s:
        try:
            from app.db.seed_skill import seed_skill

            seed_skill(s)
        except Exception as exc:  # noqa: BLE001
            print(f"技能图谱种子跳过: {exc}")
        result = seed_exams(s)
        s.commit()
        print(f"阶段测评试卷就绪: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())