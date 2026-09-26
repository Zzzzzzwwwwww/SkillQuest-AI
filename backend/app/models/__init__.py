"""SkillQuest AI 模型统一导出（Alembic autogenerate 依赖全部在此可见）。"""

from app.models.user import User
from app.models.profile import UserProfile
from app.models.learning import LearningArchive, LearningRecord
from app.models.assessment import (
    AssessmentAnswer,
    AssessmentPaper,
    AssessmentQuestion,
    AssessmentReport,
    AssessmentResult,
)
from app.models.persona import UserPersona
from app.models.skill import (
    Job,
    JobSkillRelation,
    SkillNode,
    UserSkillStatus,
)
from app.models.learning_path import (
    LearningPath,
    LearningPathNode,
    LearningProgress,
    LearningResource,
    ResourceRecommendation,
)
from app.models.chat import (
    ChatMessage,
    ChatSession,
    KnowledgeChunk,
    KnowledgeDocument,
    QaLog,
)
from app.models.assessment_review import (
    ExamAnswer,
    ExamQuestion,
    ExamRecord,
    KnowledgeMastery,
    LearningReport,
    StageExam,
)
from app.models.business_loop import BossChallenge, WeaknessDiagnostic
from app.models.gamification import (
    Achievement,
    PomodoroSession,
    UserAchievement,
    XpLog,
)

__all__ = [
    "User",
    "UserProfile",
    "LearningArchive",
    "LearningRecord",
    "AssessmentReport",
    "AssessmentPaper",
    "AssessmentQuestion",
    "AssessmentAnswer",
    "AssessmentResult",
    "UserPersona",
    "Job",
    "SkillNode",
    "JobSkillRelation",
    "UserSkillStatus",
    "LearningPath",
    "LearningPathNode",
    "LearningResource",
    "LearningProgress",
    "ResourceRecommendation",
    "ChatSession",
    "ChatMessage",
    "KnowledgeDocument",
    "KnowledgeChunk",
    "QaLog",
    "StageExam",
    "ExamQuestion",
    "ExamRecord",
    "ExamAnswer",
    "KnowledgeMastery",
    "LearningReport",
    "WeaknessDiagnostic",
    "BossChallenge",
    "Achievement",
    "UserAchievement",
    "XpLog",
    "PomodoroSession",
]