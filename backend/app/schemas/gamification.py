"""
SkillQuest AI 游戏化 Schema（模块9）。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.gamification import POMODORO_DEEP, POMODORO_FOCUS


class PomodoroIn(BaseModel):
    """番茄钟完成入参。"""

    mode: str = Field(
        POMODORO_FOCUS, description=f"专注模式 {POMODORO_FOCUS}/25min 或 {POMODORO_DEEP}/40min"
    )
    note: Optional[str] = Field(None, max_length=200, description="专注内容备注")


class PomodoroOut(BaseModel):
    """番茄钟完成出参。"""

    session_id: int
    mode: str
    focus_minutes: int
    break_minutes: int
    xp_amount: int
    message: str


class DailyTaskOut(BaseModel):
    """每日任务条目。"""

    task_id: str
    type: str
    title: str
    detail: str = ""
    xp: int = 0


class DailyTaskCompleteOut(BaseModel):
    """每日任务完成出参。"""

    task_id: str
    already_done: bool = False
    xp_amount: int = 0
    message: str = ""


class DailySupervisionOut(BaseModel):
    """每日督导出参（规则任务 + Coach Agent 增强）。"""

    tasks: List[DailyTaskOut] = []
    coach_plan: List[Dict[str, Any]] = []
    pomodoro_suggestion: Dict[str, Any] = {}
    encouragement: str = ""
    degraded: bool = True


class XpLogOut(BaseModel):
    """XP 流水条目。"""

    id: int
    action_type: str
    xp_amount: int
    note: str = ""
    created_at: Optional[str] = None


class AchievementItemOut(BaseModel):
    """成就条目。"""

    achievement_id: int
    name: str
    title: str
    description: str = ""
    icon: str = ""
    hidden: bool = False
    unlocked: bool = False
    unlocked_at: Optional[str] = None
    xp_reward: int = 0


class AchievementCenterOut(BaseModel):
    """成就中心。"""

    total: int = 0
    unlocked_count: int = 0
    items: List[AchievementItemOut] = []


class GamificationOverviewOut(BaseModel):
    """成长首页聚合出参。"""

    level: int
    tier_key: str
    tier_label: str
    tier_index: int
    tier_percent: float
    total_xp: int
    xp_to_next_level: int
    today_xp: int
    streak: int
    checked_in_today: bool
    pomodoro: Dict[str, Any] = {}
    daily_tasks: List[DailyTaskOut] = []
    achievements: AchievementCenterOut = {}
    recent_xp_logs: List[XpLogOut] = []


class CheckinOut(BaseModel):
    """每日打卡出参。"""

    already_checked: bool = False
    xp_amount: int = 0
    streak: int = 0
    message: str = ""