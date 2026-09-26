#!/usr/bin/env python3
"""独立运行：为学习资源表写入规则化种子资源。

用法：
    PYTHONPATH=. python scripts/seed_learning.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import warnings

warnings.filterwarnings("ignore")

import app.db.session as ds
from app.db.base import Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

DEMO_DB = Path(__file__).resolve().parents[1] / "sq_demo.db"


def main() -> int:
    engine = create_engine(f"sqlite:///{DEMO_DB}", connect_args={"check_same_thread": False})
    ds.engine = engine
    ds.SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    ds.check_db_health = lambda: {"connected": True}
    ds.check_redis_health = lambda: {"connected": True}

    Base.metadata.create_all(engine)

    from app.db.seed_learning import seed_learning_resources

    with ds.SessionLocal() as s:
        # 前置技能图谱（资源依赖技能节点）
        try:
            from app.db.seed_skill import seed_skill

            seed_skill(s)
        except Exception as exc:  # noqa: BLE001
            print(f"技能图谱种子跳过: {exc}")
        result = seed_learning_resources(s)
        print(f"学习资源就绪: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())