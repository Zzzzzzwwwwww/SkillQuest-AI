"""
SkillQuest AI v1 路由汇总

将各业务模块的 APIRouter 统一挂载到 /api/v1 前缀下。
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    agents,
    assessment,
    auth,
    boss,
    chat,
    exam_review,
    gamification,
    health,
    learning,
    persona,
    skills,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(assessment.router)
api_router.include_router(persona.router)
api_router.include_router(skills.jobs_router)
api_router.include_router(skills.skills_router)
api_router.include_router(learning.path_router)
api_router.include_router(learning.progress_router)
api_router.include_router(learning.resource_router)
api_router.include_router(chat.chat_router)
api_router.include_router(chat.knowledge_router)
api_router.include_router(exam_review.exam_router)
api_router.include_router(exam_review.mastery_router)
api_router.include_router(exam_review.report_router)
api_router.include_router(boss.router)
api_router.include_router(agents.router)
api_router.include_router(gamification.router)