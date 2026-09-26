"""
SkillQuest AI 业务闭环模型（模块8：全链路数据流转）

新增两张闭环支撑表：
  - weakness_diagnostics  弱点诊断（阶段测评提交后自动落库，供 AI 导师推送）
  - boss_challenges        Boss 挑战记录（完成后自动发放 XP / 升级技能等级）
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# 弱点诊断状态
DIAG_NEW = "new"          # 待处理（AI 导师待推送）
DIAG_NOTIFIED = "notified"  # 已推送
DIAG_TREATED = "treated"    # 已改善（掌握度回升后自动标记）

# Boss 挑战状态
BOSS_STARTED = "started"   # 已出题，尚未提交
BOSS_PASSED = "passed"
BOSS_FAILED = "failed"

# Boss 挑战通过/参与基础奖励
BOSS_PASS_BASE_XP = 30
BOSS_FAIL_BASE_XP = 5


class WeaknessDiagnostic(Base):
    """弱点诊断：阶段测评提交后规则判定生成，驱动 AI 导师个性化引导。"""

    __tablename__ = "weakness_diagnostics"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "record_id", "knowledge_point_id",
            name="uq_weakness_user_record_kp",
        ),
        Index("ix_weakness_user_status", "user_id", "status"),
        {"comment": "弱点诊断表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户ID",
    )
    record_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("exam_records.id", ondelete="CASCADE"),
        nullable=False,
        comment="来源测评记录ID",
    )
    knowledge_point_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("skill_nodes.id", ondelete="CASCADE"),
        nullable=True,
        default=None,
        comment="知识点ID",
    )
    kp_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="知识点名称"
    )
    domain: Mapped[str] = mapped_column(
        String(128), default="", nullable=False, comment="能力域"
    )
    mastery_score: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="当前掌握度 0-100"
    )
    diagnosis: Mapped[str] = mapped_column(
        Text, default="", nullable=False, comment="规则诊断与建议"
    )
    status: Mapped[str] = mapped_column(
        String(16), default=DIAG_NEW, nullable=False, comment="状态 new/notified/treated"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False, comment="创建时间"
    )


class BossChallenge(Base):
    """Boss 挑战记录：完成挑战 → 规则评分 → XP 发放 + 技能等级更新。"""

    __tablename__ = "boss_challenges"
    __table_args__ = (
        Index("ix_boss_user", "user_id", "created_at"),
        {"comment": "Boss挑战记录表"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户ID",
    )
    skill_node_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skill_nodes.id", ondelete="CASCADE"),
        nullable=False,
        comment="挑战技能节点ID",
    )
    skill_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="挑战技能名称"
    )
    score: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="挑战得分(百分制)"
    )
    status: Mapped[str] = mapped_column(
        String(16), default=BOSS_FAILED, nullable=False, comment="结果 passed/failed"
    )
    reward_xp: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="发放XP"
    )
    result: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, default=None, comment="挑战明细 JSON"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False, comment="创建时间"
    )