#!/usr/bin/env python3
"""
SkillQuest AI 沙箱演示启动脚本（SQLite，模块1-3 全量）

沙箱环境无 MySQL/Redis，本脚本用 SQLite 文件库代替 MySQL：
  1. 建全部表（create_all，与 Alembic 迁移等价）
  2. 写入内置职业测评试卷
  3. 写入一个演示账号 hunter / skillquest123
  4. 启动 uvicorn（监听 0.0.0.0）

用法：
    PYTHONPATH=. python scripts/run_demo_sqlite.py --port 3900
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import warnings

warnings.filterwarnings("ignore")

# SQLite 替身：BigInteger 主键编译为 INTEGER 以获得自增长
from sqlalchemy import BigInteger
from sqlalchemy.ext.compiler import compiles


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(type_, compiler, **kw):
    return "INTEGER"


import app.db.session as ds
from app.db.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DEMO_DB = Path(__file__).resolve().parents[1] / "sq_demo.db"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=3900)
    parser.add_argument("--db", type=str, default=str(DEMO_DB))
    args = parser.parse_args()

    # ---- 替换 MySQL 为 SQLite 文件库 ----
    engine = create_engine(
        f"sqlite:///{args.db}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    ds.engine = engine
    ds.SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    ds.check_db_health = lambda: {"connected": True}
    ds.check_redis_health = lambda: {"connected": True}

    Base.metadata.create_all(engine)

    # ---- 种子：试卷 + 技能图谱 + 学习资源 + 阶段测评 + 演示账号 ----
    from app.db.seed_assessment import seed_assessment
    from app.db.seed_exam import seed_exams
    from app.db.seed_skill import seed_skill
    from app.db.seed_learning import seed_learning_resources
    from app.core.security import hash_password
    from app.models.user import User, USER_STATUS_NORMAL
    from app.models.profile import UserProfile
    from app.models.learning import LearningArchive
    from sqlalchemy import select

    with ds.SessionLocal() as s:
        seed_assessment(s)
        seed_skill(s)
        seed_learning_resources(s)
        seed_exams(s)
        from app.db.seed_gamification import seed_achievements

        seed_achievements(s)
        user = s.scalar(select(User).where(User.username == "hunter"))
        if user is None:
            user = User(
                username="hunter",
                email="hunter@example.com",
                password_hash=hash_password("skillquest123"),
                status=USER_STATUS_NORMAL,
            )
            s.add(user)
            s.flush()
            s.add(UserProfile(user_id=user.id))
            s.add(LearningArchive(user_id=user.id, archive_name="我的成长档案"))
        s.commit()

    # 模块6：答疑知识库种子（async 内部切分+向量化）
    import asyncio

    from app.db.seed_knowledge import seed_chat_knowledge

    with ds.SessionLocal() as s:
        asyncio.run(seed_chat_knowledge(s))

    print(f"演示库就绪: {args.db}（演示账号 hunter / skillquest123）")

    # ---- 启动 uvicorn（完整模块1-4） ----
    import uvicorn
    from app.main import app

    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())