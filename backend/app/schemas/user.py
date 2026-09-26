"""
SkillQuest AI 用户相关 Schema（Pydantic v2）

提供注册 / 登录 / 用户信息 / 令牌 / 画像 / 档案 / 轨迹 / 报告等数据契约。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------- #
# 认证
# ---------------------------------------------------------------- #
class UserCreate(BaseModel):
    """注册请求体。"""

    username: str = Field(min_length=3, max_length=64, description="用户名，3-64 个字符")
    email: EmailStr = Field(description="邮箱，需为合法邮箱格式")
    password: str = Field(min_length=6, max_length=128, description="密码，至少 6 位")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "username": "skill_learner",
            "email": "learner@example.com",
            "password": "password123",
        }
    })


class UserLogin(BaseModel):
    """登录请求体（支持用户名或邮箱登录）。"""

    account: str = Field(min_length=1, description="用户名或邮箱")
    password: str = Field(min_length=1, description="登录密码")

    model_config = ConfigDict(json_schema_extra={
        "example": {"account": "skill_learner", "password": "password123"}
    })


class UserOut(BaseModel):
    """用户信息出参（安全字段，不含密码哈希）。"""

    id: int
    username: str
    email: EmailStr
    phone: Optional[str] = None
    avatar: Optional[str] = None
    status: int = 1
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenOut(BaseModel):
    """令牌 + 用户信息出参。"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class MessageOut(BaseModel):
    """通用消息出参。"""

    message: str


# ---------------------------------------------------------------- #
# 个人信息更新
# ---------------------------------------------------------------- #
class ProfileUpdate(BaseModel):
    """用户画像更新请求体（全部可选，仅更新传入字段）。"""

    real_name: Optional[str] = Field(default=None, max_length=64, description="真实姓名")
    education: Optional[str] = Field(default=None, max_length=32, description="学历")
    major: Optional[str] = Field(default=None, max_length=64, description="专业")
    school: Optional[str] = Field(default=None, max_length=128, description="学校")
    company: Optional[str] = Field(default=None, max_length=128, description="公司")
    job_intention: Optional[str] = Field(default=None, max_length=128, description="求职意向岗位")
    learning_goal: Optional[str] = Field(default=None, max_length=1000, description="学习目标")
    daily_study_time: Optional[int] = Field(default=None, ge=5, le=480, description="每日学习时长(分钟)")
    phone: Optional[str] = Field(default=None, max_length=20, description="手机号")
    avatar: Optional[str] = Field(default=None, max_length=512, description="头像URL")


class ProfileOut(BaseModel):
    """用户画像出参。"""

    id: int
    user_id: int
    real_name: Optional[str] = None
    education: Optional[str] = None
    major: Optional[str] = None
    school: Optional[str] = None
    company: Optional[str] = None
    job_intention: Optional[str] = None
    learning_goal: Optional[str] = None
    daily_study_time: int = 30
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserWithProfileOut(BaseModel):
    """用户信息 + 画像合并出参（GET /api/users/me 使用）。"""

    id: int
    username: str
    email: EmailStr
    phone: Optional[str] = None
    avatar: Optional[str] = None
    status: int = 1
    created_at: datetime
    updated_at: datetime
    profile: Optional[ProfileOut] = None


# ---------------------------------------------------------------- #
# 学习档案 / 轨迹 / 报告
# ---------------------------------------------------------------- #
class LearningArchiveOut(BaseModel):
    """学习档案出参。"""

    id: int
    user_id: int
    archive_name: str
    target_job: Optional[str] = None
    current_level: int = 1
    total_xp: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArchiveOverviewOut(LearningArchiveOut):
    """档案 + 学习统计概览（规则计算的总览信息）。"""

    total_records: int = 0          # 学习记录总数
    total_duration: int = 0         # 总学习时长(秒)
    finished_count: int = 0         # 完成类动作次数
    xp_to_next_level: int = 0       # 距下一等级还需 XP（规则计算）


class LearningRecordOut(BaseModel):
    """学习轨迹出参。"""

    id: int
    user_id: int
    module_type: str
    action_type: str
    target_id: Optional[int] = None
    duration: int = 0
    result: Optional[dict] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssessmentReportOut(BaseModel):
    """测评报告出参。"""

    id: int
    user_id: int
    assessment_id: Optional[int] = None
    report_type: str
    report_json: dict
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)