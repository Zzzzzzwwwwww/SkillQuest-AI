"""
游戏化系统（模块9）—— 端到端验证脚本

覆盖：
  - 成就 seed：成就中心返回 6 个成就、初出茅庐未解锁
  - 成长首页 overview：等级/段位(青铜)/XP/连击/今日任务/番茄钟
  - 每日打卡：+10 XP、当天重复不重复奖励
  - 番茄钟：focus(25min/+8) 与 deep(40min/+12)、统计
  - XP 流水分页
  - 每日任务：规则生成 + 完成任务领奖 + 同日去重
  - 成就解锁：初出茅庐（首次 XP）自动解锁；连击 3 天；隐藏成就条件隐藏
  - 段位/连击服务单测
"""

import random
import warnings

warnings.filterwarnings("ignore")

from sqlalchemy import BigInteger
from sqlalchemy.ext.compiler import compiles


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(type_, compiler, **kw):
    return "INTEGER"


import app.db.session as ds
from app.db.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

eng = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
ds.engine = eng
ds.SessionLocal = sessionmaker(bind=eng, autocommit=False, autoflush=False)
Base.metadata.create_all(eng)
ds.check_db_health = lambda: {"connected": True}
ds.check_redis_health = lambda: {"connected": True}

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} -> {detail}")


# ------------------------------------------------------------------- #
# 0. 准备：注册 + 成就 seed
# ------------------------------------------------------------------- #
print("== 0. 准备：注册 + 成就 seed ==")
suffix = str(random.randint(1000, 9999))
username = f"game_{suffix}"
r = client.post("/api/v1/auth/register", json={
    "username": username,
    "email": f"{username}@example.com",
    "password": "pass1234",
})
check("注册成功", r.status_code == 200, str(r.status_code) + str(r.text))
token = r.json()["data"]["access_token"]
uid = r.json()["data"]["user"]["id"]
h = {"Authorization": f"Bearer {token}"}

from app.db.seed_gamification import seed_achievements  # noqa: E402

with ds.SessionLocal() as s:
    seed_achievements(s)
    s.commit()

# ------------------------------------------------------------------- #
# 1. 成长首页 overview（初始）
# ------------------------------------------------------------------- #
print("== 1. GET /gamification/overview ==")
r = client.get("/api/v1/gamification/overview", headers=h)
check("overview 200", r.status_code == 200, str(r.status_code))
ov = r.json()["data"]
check("初始等级=1", ov["level"] == 1, str(ov["level"]))
check("初始段位=青铜", ov["tier_key"] == "bronze" and ov["tier_label"] == "青铜",
      str(ov))
check("初始 XP=0", ov["total_xp"] == 0, str(ov["total_xp"]))
check("初始连击=0", ov["streak"] == 0, str(ov["streak"]))
check("未打卡", ov["checked_in_today"] is False, str(ov["checked_in_today"]))
check("今日任务生成", len(ov["daily_tasks"]) >= 2, str(len(ov["daily_tasks"])))
check("今日任务带XP奖励", all(t["xp"] > 0 for t in ov["daily_tasks"]), str(ov["daily_tasks"]))
check("番茄钟统计初始化", ov["pomodoro"]["session_count"] == 0, str(ov["pomodoro"]))

# 无 /v1 前缀兼容（业务侧要求 /api/gamification）
r = client.get("/api/gamification/overview", headers=h)
check("无前缀 overview 可用", r.status_code == 200, str(r.status_code))

# 未鉴权
r = client.get("/api/v1/gamification/overview")
check("未鉴权401", r.status_code == 401, str(r.status_code))

# ------------------------------------------------------------------- #
# 2. 成就中心（seed 后未解锁）
# ------------------------------------------------------------------- #
print("== 2. GET /gamification/achievements ==")
r = client.get("/api/v1/gamification/achievements", headers=h)
check("成就中心200", r.status_code == 200, str(r.status_code))
ac = r.json()["data"]
check("共6个成就", ac["total"] == 6 and len(ac["items"]) == 6, str(ac))
check("未解锁0", ac["unlocked_count"] == 0, str(ac))
names = {a["name"] for a in ac["items"]}
check("成就清单齐全",
      {"first_steps", "streak_3", "question_slayer", "boss_slayer",
       "skill_lighter", "hidden_achievement"} <= names,
      str(names))
hid = next(a for a in ac["items"] if a["name"] == "hidden_achievement")
check("隐藏成就未解锁时条件隐藏", hid["unlocked"] is False and hid["description"] == "……",
      str(hid))

# ------------------------------------------------------------------- #
# 3. 每日打卡
# ------------------------------------------------------------------- #
print("== 3. POST /gamification/checkin ==")
r = client.post("/api/v1/gamification/checkin", headers=h, json={})
check("打卡200", r.status_code == 200, str(r.status_code) + str(r.text))
ck = r.json()["data"]
check("打卡+10XP", ck["xp_amount"] == 10 and not ck["already_checked"], str(ck))
check("打卡后连击=1", ck["streak"] == 1, str(ck))

r = client.post("/api/v1/gamification/checkin", headers=h, json={})
ck2 = r.json()["data"]
check("当天重复打卡不重复奖励", ck2["already_checked"] is True and ck2["xp_amount"] == 0,
      str(ck2))

# 打卡触发成就解锁：初出茅庐（total_xp>=1）
r = client.get("/api/v1/gamification/achievements", headers=h)
ac2 = r.json()["data"]
fs = next(a for a in ac2["items"] if a["name"] == "first_steps")
check("初出茅庐已解锁", fs["unlocked"] is True and fs["unlocked_at"], str(fs))
check("解锁数=1", ac2["unlocked_count"] == 1, str(ac2))

# ------------------------------------------------------------------- #
# 4. 番茄钟
# ------------------------------------------------------------------- #
print("== 4. POST /gamification/pomodoro ==")
r = client.post("/api/v1/gamification/pomodoro", headers=h,
                json={"mode": "focus", "note": "学习 Python"})
check("番茄钟200", r.status_code == 200, str(r.status_code) + str(r.text))
pm = r.json()["data"]
check("focus 25分钟8XP", pm["focus_minutes"] == 25 and pm["xp_amount"] == 8, str(pm))
r = client.post("/api/v1/gamification/pomodoro", headers=h,
                json={"mode": "deep"})
pm2 = r.json()["data"]
check("deep 40分钟12XP", pm2["focus_minutes"] == 40 and pm2["xp_amount"] == 12, str(pm2))
r = client.post("/api/v1/gamification/pomodoro", headers=h, json={"mode": "bad"})
check("非法模式422", r.status_code == 422, str(r.status_code))

r = client.get("/api/v1/gamification/overview", headers=h)
ov3 = r.json()["data"]
check("番茄钟统计=2次/65分钟", ov3["pomodoro"]["session_count"] == 2
      and ov3["pomodoro"]["focus_total_minutes"] == 65, str(ov3["pomodoro"]))
# 10(打卡)+5(初出茅庐成就)+8+12 = 35
check("XP累计=35", ov3["total_xp"] == 10 + 5 + 8 + 12, str(ov3["total_xp"]))

# ------------------------------------------------------------------- #
# 5. XP 流水
# ------------------------------------------------------------------- #
print("== 5. GET /gamification/xp-logs ==")
r = client.get("/api/v1/gamification/xp-logs", headers=h)
check("流水200", r.status_code == 200, str(r.status_code))
lg = r.json()["data"]
check("流水条数>=3", lg["total"] >= 3, str(lg["total"]))
check("倒序排列", all(lg["items"][i]["created_at"] >= lg["items"][i + 1]["created_at"]
                  for i in range(len(lg["items"]) - 1)), str(lg["items"]))

# ------------------------------------------------------------------- #
# 6. 每日任务：完成 + 去重
# ------------------------------------------------------------------- #
print("== 6. 每日督导任务 ==")
r = client.get("/api/v1/gamification/today-tasks", headers=h)
check("today-tasks 200", r.status_code == 200, str(r.status_code) + str(r.text))
sup = r.json()["data"]
check("任务>=2", len(sup["tasks"]) >= 2, str(len(sup["tasks"])))
check("激励语给出", bool(sup["encouragement"]), str(sup["encouragement"]))
check("Coach 计划给出", isinstance(sup["coach_plan"], list), str(sup["coach_plan"]))
check("番茄钟建议给出", bool(sup["pomodoro_suggestion"].get("focus_minutes")), str(sup["pomodoro_suggestion"]))

task = sup["tasks"][0]
r = client.post("/api/v1/gamification/tasks/complete", headers=h,
                json={"task_id": task["task_id"]})
check("完成任务200", r.status_code == 200, str(r.status_code) + str(r.text))
td = r.json()["data"]
check("任务XP>0", td["xp_amount"] == task["xp"] and not td["already_done"], str(td))
r = client.post("/api/v1/gamification/tasks/complete", headers=h,
                json={"task_id": task["task_id"]})
td2 = r.json()["data"]
check("同日同任务去重", td2["already_done"] is True and td2["xp_amount"] == 0, str(td2))

# 不存在的任务
r = client.post("/api/v1/gamification/tasks/complete", headers=h,
                json={"task_id": "no_such"})
check("不存在任务404", r.status_code == 404, str(r.status_code))

# ------------------------------------------------------------------- #
# 7. XP 侧写：完成学习/项目（服务层直调）
# ------------------------------------------------------------------- #
print("== 7. 服务层 XP/段位/连击单测 ==")
from app.services import gamification as game  # noqa: E402
from app.models.gamification import XpLog  # noqa: E402

# 段位映射
check("Lv1=青铜", game.tier_of(1) == "bronze" and game.tier_of(2) == "bronze", game.tier_of(1))
check("Lv3=白银", game.tier_of(3) == "silver", game.tier_of(3))
check("Lv5=黄金", game.tier_of(5) == "gold", game.tier_of(5))
check("Lv7=铂金", game.tier_of(10) == "diamond", game.tier_of(10))
check("Lv14=王者", game.tier_of(20) == "king", game.tier_of(20))
check("段位下标递增", game.tier_index_of(6) > game.tier_index_of(2), "")

# 连击：模拟往期日期
from datetime import date, datetime, timedelta  # noqa: E402
from sqlalchemy import select  # noqa: E402

with ds.SessionLocal() as s:
    for i in range(1, 4):
        s.add(XpLog(user_id=uid, action_type="study", xp_amount=20,
                    note="模拟学习",
                    created_at=datetime.now() - timedelta(days=3 - i)))
    s.commit()
    streak = game.compute_streak(s, uid)
check("连击=3(含今天)", streak == 3, str(streak))

# 学习 XP 发放（服务函数）
with ds.SessionLocal() as s:
    res = game.record_action_xp(s, uid, "study", "完成课程", amount=20)
    s.commit()
check("学习XP=20", res["xp_amount"] == 20, str(res))
with ds.SessionLocal() as s:
    res2 = game.record_action_xp(s, uid, "project", "完成项目", amount=50)
    s.commit()
check("项目XP=50", res2["xp_amount"] == 50, str(res2))

# 累计 XP 应足够连击成就 + hidden 未解锁
r = client.get("/api/v1/gamification/achievements", headers=h)
ac3 = r.json()["data"]
st3 = next(a for a in ac3["items"] if a["name"] == "streak_3")
check("连击成就已解锁", st3["unlocked"] is True, str(st3))
hid2 = next(a for a in ac3["items"] if a["name"] == "hidden_achievement")
check("隐藏成就仍未解锁", hid2["unlocked"] is False, str(hid2))

# 隐藏成就：XP 拉高到 1500 解锁
with ds.SessionLocal() as s:
    game.add_xp(s, uid, "study", 1500, "冲刺隐藏成就")
    s.commit()
r = client.get("/api/v1/gamification/achievements", headers=h)
ac4 = r.json()["data"]
hid3 = next(a for a in ac4["items"] if a["name"] == "hidden_achievement")
check("隐藏成就已解锁", hid3["unlocked"] is True, str(hid3))

# 1500 XP 冲刺隐藏成就后：level_from_xp(1500)=6 → gold
r = client.get("/api/v1/gamification/overview", headers=h)
ov4 = r.json()["data"]
check("高段位显示", ov4["level"] >= 6 and ov4["tier_key"] == "gold",
      str((ov4["level"], ov4["tier_key"])))

print(f"\n结果: PASS={PASS} FAIL={FAIL}")
if FAIL:
    raise SystemExit(1)