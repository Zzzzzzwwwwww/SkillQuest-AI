"""
SkillQuest AI 健康检查接口

GET /api/v1/health
  对应用基础可用性做探测，返回 MySQL / Redis 的实时连接状态。
"""

from fastapi import APIRouter

from app.core.config import settings
from app.core.response import success
from app.db.session import check_db_health, check_redis_health

router = APIRouter(tags=["health"])


@router.get("/health", summary="服务健康检查")
def health_check() -> dict:
    """
    健康检查（不依赖外部服务，服务进程本身可存活即可返回 200）：
      - app:   应用名与版本
      - db:    MySQL 连接状态（connected / error）
      - redis: Redis 连接状态（connected / error）
      - time:  服务器当前时间（UTC）
    """
    return success(
        data={
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "ok",
            "db": check_db_health(),
            "redis": check_redis_health(),
            "time": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        },
        message="service alive",
    )