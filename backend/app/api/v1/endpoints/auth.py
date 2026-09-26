"""
SkillQuest AI 认证接口（模块2：用户管理）

  - POST /api/auth/register  注册：bcrypt 加密、初始化画像与学习档案、签发 JWT
  - POST /api/auth/login     登录：用户名/邮箱 + 密码，签发 JWT

统一错误处理：唯一性冲突 400、账号密码错误 400、账号禁用 403、鉴权失败 401。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.response import success
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.learning import LearningArchive
from app.models.profile import UserProfile
from app.models.user import User, USER_STATUS_DISABLED, USER_STATUS_NORMAL
from app.schemas.common import ApiResponse
from app.schemas.user import (
    TokenOut,
    UserCreate,
    UserLogin,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=ApiResponse[TokenOut],
    summary="用户注册",
    description="注册并自动完成：用户创建、画像初始化、学习档案初始化、JWT 签发。",
)
def register(user_in: UserCreate, db: Session = Depends(get_db)) -> dict:
    """注册：用户名/邮箱唯一性校验 → bcrypt 哈希 → 落库 → 初始化档案 → 签发 JWT。"""
    username = user_in.username.strip()
    email = user_in.email.strip().lower()

    exists = db.scalar(
        select(User.id).where(or_(User.username == username, User.email == email))
    )
    if exists is not None:
        raise HTTPException(status_code=400, detail="用户名或邮箱已被注册")

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(user_in.password),
        status=USER_STATUS_NORMAL,
    )
    db.add(user)
    db.flush()  # 获得 user.id

    # 初始化画像（一对一）
    profile = UserProfile(user_id=user.id)
    db.add(profile)

    # 初始化学习档案（默认为基础档案）
    archive = LearningArchive(
        user_id=user.id,
        archive_name="我的成长档案",
        target_job=None,
        current_level=1,
        total_xp=0,
    )
    db.add(archive)
    db.commit()

    return success(build_token_response(user))


@router.post(
    "/login",
    response_model=ApiResponse[TokenOut],
    summary="用户登录",
    description="使用用户名或邮箱 + 密码登录，签发 JWT。",
)
def login(user_in: UserLogin, db: Session = Depends(get_db)) -> dict:
    """登录：按用户名或邮箱匹配用户，校验密码与状态，签发 JWT。"""
    account = user_in.account.strip()

    user = db.scalar(
        select(User).where(or_(User.username == account, User.email == account))
    )
    # 统一提示，避免暴露账号是否存在
    if user is None or not verify_password(user_in.password, user.password_hash):
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    if user.status == USER_STATUS_DISABLED:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    return success(build_token_response(user))


def build_token_response(user: User) -> TokenOut:
    """构造令牌响应：签发 JWT 并附带用户信息。"""
    access_token = create_access_token(subject=user.id)
    return TokenOut(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )