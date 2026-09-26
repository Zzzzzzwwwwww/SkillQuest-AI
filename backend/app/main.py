"""
SkillQuest AI FastAPI 应用入口

启动命令：
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Swagger 文档：
    http://127.0.0.1:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.api.v1.endpoints.learning import (
    path_router as learning_path_router,
    progress_router as learning_progress_router,
    resource_router as learning_resource_router,
)
from app.api.v1.endpoints.chat import (
    chat_router,
    knowledge_router,
)
from app.api.v1.endpoints.boss import router as boss_router
from app.api.v1.endpoints.agents import router as agents_router
from app.api.v1.endpoints.gamification import router as gamification_router
from app.api.v1.endpoints.exam_review import (
    exam_router,
    mastery_router,
    report_router,
)
from app.core.config import settings
from app.core.response import register_exception_handlers
from app.db.session import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化，关闭时释放资源。"""
    # ---------- 启动阶段 ----------
    try:
        redis_client.ping()
        print("[SkillQuest AI] Redis 连接正常")
    except Exception as exc:  # noqa: BLE001
        print(f"[SkillQuest AI] 警告: Redis 暂不可用 -> {exc}")

    yield

    # ---------- 关闭阶段 ----------
    redis_client.close()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "SkillQuest AI —— AI 职业成长智能体后端服务。"
        "融合职业规划、技能图谱、AI 导师、自适应学习与 RPG 游戏化成长。"
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
)

# ---------- CORS 跨域 ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- 统一响应 / 异常处理 ----------
register_exception_handlers(app)

# ---------- 路由挂载 ----------
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# 个性化导学模块兼容非 /v1 前缀（业务侧要求 /api/learning-path、/api/learning-progress、/api/learning-resources）
app.include_router(learning_path_router, prefix="/api")
app.include_router(learning_progress_router, prefix="/api")
app.include_router(learning_resource_router, prefix="/api")

# 智能答疑模块兼容非 /v1 前缀（业务侧要求 /api/chat、/api/knowledge）
app.include_router(chat_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")

# 学习评估复盘模块兼容非 /v1 前缀（业务侧要求 /api/exam、/api/mastery、/api/report）
app.include_router(exam_router, prefix="/api")
app.include_router(mastery_router, prefix="/api")
app.include_router(report_router, prefix="/api")

# Boss 挑战模块兼容非 /v1 前缀（业务侧要求 /api/boss）
app.include_router(boss_router, prefix="/api")

# 统一多智能体模块兼容非 /v1 前缀（业务侧要求 /api/agents）
app.include_router(agents_router, prefix="/api")

# 游戏化模块兼容非 /v1 前缀（业务侧要求 /api/gamification）
app.include_router(gamification_router, prefix="/api")


@app.get("/", tags=["root"], summary="服务根路径")
def root() -> dict:
    """根路径探针，返回应用基本信息。"""
    from app.core.response import success

    return success(
        data={
            "app": settings.APP_NAME,
            "docs": "/docs",
            "health": f"{settings.API_V1_PREFIX}/health",
        }
    )