"""
SkillQuest AI 安全模块

提供：
  - 密码哈希 / 校验（bcrypt）
  - JWT 令牌的生成与解析
  - 鉴权依赖 get_current_user（解码 JWT 并加载数据库用户）
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User, USER_STATUS_DISABLED

# ---------- 密码哈希（bcrypt） ----------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """对明文密码进行哈希。"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    return pwd_context.verify(plain_password, password_hash)


# ---------- JWT ----------
bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(
    subject: str | int,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    """签发 JWT 访问令牌。

    Args:
        subject: 用户标识（如用户 ID 或用户名）。
        expires_delta: 有效期；为空则使用配置中的默认时长。
        extra_claims: 附加声明（如 role）。

    Returns:
        编码后的 JWT 字符串。
    """
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """解析并校验 JWT 令牌，返回其中携带的声明。"""
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录状态已过期，请重新登录",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的访问令牌",
        ) from exc


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """鉴权依赖：校验 JWT 并从数据库加载当前用户实体。

    用法：
        def me(user: User = Depends(get_current_user)): ...
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少身份认证信息",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    try:
        user_id = int(payload.get("sub", ""))
    except (TypeError, ValueError):
        user_id = 0

    user = db.get(User, user_id) if user_id > 0 else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被删除",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.status == USER_STATUS_DISABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )
    return user