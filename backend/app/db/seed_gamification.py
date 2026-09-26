"""
SkillQuest AI 游戏化成就种子数据（模块9）

成就清单（条件由 condition_json 规则引擎读取，服务层统一校验）：
  1. first_steps       初出茅庐     —— 首次获得 XP
  2. streak_3          连续学习     —— 连击打卡 3 天
  3. question_slayer   问题终结者   —— AI 导师答疑提问满 10 次
  4. boss_slayer       Boss Slayer —— 通过任意 Boss 挑战
  5. skill_lighter     技能树点亮者 —— 技能掌握度达 80 的节点 ≥ 5 个
  6. hidden_achievement 隐藏成就    —— 累计 XP 达 1500（未解锁时隐藏条件）

测试与生产复用：seed_achievements(db) 幂等 upsert（按 name）。
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.gamification import Achievement

# (name, title, description, icon, condition, xp_reward, hidden, sort)
ACHIEVEMENT_DEFS = [
    (
        "first_steps",
        "初出茅庐",
        "获得你的第一笔经验值，开启成长之旅。",
        "trophy",
        {"type": "total_xp", "min": 1},
        5,
        0,
        1,
    ),
    (
        "streak_3",
        "连续学习",
        "连续 3 天打卡学习，保持节奏。",
        "calendar",
        {"type": "streak", "min": 3},
        10,
        0,
        2,
    ),
    (
        "question_slayer",
        "问题终结者",
        "向 AI 导师提问 10 次，把问题一个个解决掉。",
        "chat",
        {"type": "qa_count", "min": 10},
        15,
        0,
        3,
    ),
    (
        "boss_slayer",
        "Boss Slayer",
        "通过任意一次 Boss 挑战（得分 ≥ 60）。",
        "sword",
        {"type": "boss_pass", "min": 1},
        20,
        0,
        4,
    ),
    (
        "skill_lighter",
        "技能树点亮者",
        "掌握度达 80 的技能点亮 5 个节点。",
        "star",
        {"type": "mastered_skills", "min": 5},
        25,
        0,
        5,
    ),
    (
        "hidden_achievement",
        "隐藏成就",
        "累计经验值达到 1500，解锁未公开的隐藏称谓。",
        "medal",
        {"type": "total_xp", "min": 1500},
        50,
        1,
        6,
    ),
]


DEFAULT_ACHIEVEMENTS = ACHIEVEMENT_DEFS


def seed_achievements(db: Session) -> int:
    """幂等写入成就定义（按 name upsert，返回成就数量）。"""
    count = 0
    for name, title, desc, icon, cond, xp_reward, hidden, sort in ACHIEVEMENT_DEFS:
        exist: Optional[Achievement] = db.scalar(
            select(Achievement).where(Achievement.name == name)
        )
        if exist is None:
            db.add(
                Achievement(
                    name=name,
                    title=title,
                    description=desc,
                    icon=icon,
                    condition_json=cond,
                    xp_reward=xp_reward,
                    hidden=hidden,
                    sort_order=sort,
                )
            )
            count += 1
        else:
            exist.title = title
            exist.description = desc
            exist.icon = icon
            exist.condition_json = cond
            exist.xp_reward = xp_reward
            exist.hidden = hidden
            exist.sort_order = sort
    if count:
        db.flush()
    return count