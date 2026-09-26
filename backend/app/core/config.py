"""
SkillQuest AI 全局配置模块

基于 pydantic-settings 读取环境变量（.env），集中管理：
  - MySQL 数据库
  - Redis 缓存
  - JWT 鉴权
  - 华为云大模型（盘古）服务
  - CORS 跨域
"""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置：字段全部可从环境变量 / .env 文件覆盖。"""

    # ---------- 基础信息 ----------
    APP_NAME: str = "SkillQuest AI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = Field(default=True, description="是否开启调试模式")
    API_V1_PREFIX: str = "/api/v1"

    # ---------- MySQL ----------
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "skillquest"
    MYSQL_PASSWORD: str = "skillquest"
    MYSQL_DATABASE: str = "skillquest"

    @property
    def DATABASE_URL(self) -> str:
        """组装 SQLAlchemy 连接串（使用 PyMySQL 驱动）。"""
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            f"?charset=utf8mb4"
        )

    # ---------- Redis ----------
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    @property
    def REDIS_URL(self) -> str:
        """组装 Redis 连接串。"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ---------- JWT ----------
    JWT_SECRET_KEY: str = "skillquest-secret-key-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 默认 7 天

    # ---------- 华为云大模型（盘古 / ModelArts） ----------
    HUAWEI_LLM_ENDPOINT: str = "https://api.modelarts.yourregion.myhuaweicloud.com"
    HUAWEI_LLM_API_KEY: str = ""
    HUAWEI_LLM_MODEL: str = "pangu-5b-chat"
    HUAWEI_LLM_AUTH_TYPE: str = "apig"

    # ---------- 华为云 Embedding（RAG 向量化，未配置时规则向量降级） ----------
    HUAWEI_EMBEDDING_ENDPOINT: str = ""
    HUAWEI_EMBEDDING_API_KEY: str = ""
    HUAWEI_EMBEDDING_MODEL: str = "text-embedding-v2"
    HUAWEI_EMBEDDING_DIM: int = 256

    # ---------- 向量库 PgVector（预留） ----------
    PGVECTOR_HOST: str = "127.0.0.1"
    PGVECTOR_PORT: int = 5432
    PGVECTOR_USER: str = "skillquest"
    PGVECTOR_PASSWORD: str = "skillquest"
    PGVECTOR_DATABASE: str = "skillquest_vector"

    # ---------- CORS ----------
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:80",
        "http://127.0.0.1:80",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """返回全局单例配置对象（缓存，避免重复读取文件）。"""
    return Settings()


settings = get_settings()