"""
SkillQuest AI 用户画像模型（模块3：职业测评与画像）

表结构 user_personas（一对一用户画像，直接驱动个性化与游戏化）：
  - persona_tags_json    画像标签（含规则标签 + AI 增强的综述/优势/短板，见 services）
  - ability_radar_json   能力雷达图数据 {dimensions: [{name, score}]}（规则计算）
  - interest_json        兴趣数据（测评中兴趣维度答题解析 + 用户上报）
  - values_json          职业价值观数据（测评中价值观维度答题解析）
  - learning_goal        学习目标（规则汇总测评简答 + 画像维护）
  - target_job           目标职业（推荐结果 Top1 与用户意向综合）
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class UserPersona(Base, TimestampMixin):
    """用户画像：由职业测评结果与规则/Agent 综合生成。"""

    __tablename__ = "user_personas"
    __table_args__ = {"comment": "用户画像表"}

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        unique=True,
        nullable=False,
        comment="用户ID",
    )
    persona_tags_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="画像标签/综述/优势/短板(JSON)"
    )
    ability_radar_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="能力雷达图数据(JSON)"
    )
    interest_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, default=None, comment="兴趣数据(JSON)"
    )
    values_json: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, default=None, comment="职业价值观数据(JSON)"
    )
    learning_goal: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default=None, comment="学习目标"
    )
    target_job: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, default=None, comment="目标职业"
    )