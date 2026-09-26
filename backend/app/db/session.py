"""
SkillQuest AI 数据库会话模块

  - SQLAlchemy 2.0 Engine / SessionLocal（MySQL，PyMySQL 驱动）
  - Redis 连接池
  - FastAPI 依赖 get_db 提供请求级会话
"""

import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import settings

# ---------- SQLAlchemy Engine ----------
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # 取连接前先探测，避免 mysql 断连后的陈旧连接
    pool_recycle=3600,    # 连接复用不超过 1 小时
)

# ---------- 会话工厂 ----------
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=True,
)


def get_db():
    """FastAPI 依赖：提供请求级数据库会话，请求结束后自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- Redis ----------
redis_client: redis.Redis = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=3,
    socket_timeout=3,
)


def get_redis() -> redis.Redis:
    """FastAPI 依赖：提供共享的 Redis 客户端。"""
    return redis_client


def check_db_health() -> dict:
    """探测 MySQL 连通性（供健康检查接口使用）。"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"connected": True}
    except Exception as exc:  # noqa: BLE001
        return {"connected": False, "error": str(exc)}


def check_redis_health() -> dict:
    """探测 Redis 连通性（供健康检查接口使用）。"""
    try:
        redis_client.ping()
        return {"connected": True}
    except Exception as exc:  # noqa: BLE001
        return {"connected": False, "error": str(exc)}