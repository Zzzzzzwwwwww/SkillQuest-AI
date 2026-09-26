"""
模块2 用户管理 —— 端到端验证脚本（临时，不入仓库）

数据库连接使用内存 SQLite（StaticPool 保共享连接）替代 MySQL，
验证注册 → 登录 → me → 更新画像 → 档案 → 记录 → 报告 完整闭环。
生产环境数据库行为由 Alembic 迁移 + MySQL 保证。
"""

import warnings

warnings.filterwarnings("ignore")

# SQLite 替身兼容：BigInteger 主键在 SQLite 下编译为 INTEGER 以获得自增长
from sqlalchemy import BigInteger
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import INTEGER


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(type_, compiler, **kw):
    return "INTEGER"


import app.db.session as ds
from app.db.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 用内存 SQLite 替换 MySQL
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


print("== 1. 注册 ==")
r = client.post("/api/v1/auth/register", json={
    "username": "quant", "email": "quant@example.com", "password": "secret123",
})
check("注册返回200", r.status_code == 200, str(r.status_code))
body = r.json()
check("统一响应 code=0", body.get("code") == 0, str(body))
check("包含 access_token", bool(body["data"].get("access_token")))
token = body["data"]["access_token"]
uid = body["data"]["user"]["id"]
h = {"Authorization": f"Bearer {token}"}

print("== 2. 重复注册拦截 ==")
r2 = client.post("/api/v1/auth/register", json={
    "username": "quant", "email": "quant@example.com", "password": "secret123",
})
check("重复注册 400", r2.status_code == 400)

print("== 3. 登录 ==")
r = client.post("/api/v1/auth/login", json={"account": "quant", "password": "secret123"})
check("用户名登录成功", r.status_code == 200 and r.json()["data"]["user"]["username"] == "quant")
r = client.post("/api/v1/auth/login", json={"account": "quant@example.com", "password": "secret123"})
check("邮箱登录成功", r.status_code == 200)
r = client.post("/api/v1/auth/login", json={"account": "quant", "password": "wrong"})
check("密码错误 400", r.status_code == 400)

print("== 4. 无 token 访问受保护接口 ==")
r = client.get("/api/v1/users/me")
check("无 token 401", r.status_code == 401)

print("== 5. GET /users/me ==")
r = client.get("/api/v1/users/me", headers=h)
check("me 返回200", r.status_code == 200)
me = r.json()["data"]
check("me 包含画像(default)", me.get("profile") is not None)

print("== 6. PUT /users/profile ==")
r = client.put("/api/v1/users/profile", headers=h, json={
    "real_name": "量子", "major": "计算机科学", "school": "SkillQuest 大学",
    "job_intention": "AI 应用开发工程师", "daily_study_time": 90,
    "phone": "13800000000",
})
check("更新画像200", r.status_code == 200)
p = r.json()["data"]
check("画像字段生效", p["real_name"] == "量子" and p["daily_study_time"] == 90, str(p))
check("phone 同步到 users", client.get("/api/v1/users/me", headers=h).json()["data"]["phone"] == "13800000000")

print("== 7. GET /users/learning-archive ==")
r = client.get("/api/v1/users/learning-archive", headers=h)
check("档案200", r.status_code == 200)
ar = r.json()["data"]
check("初始等级1/XP0/统计0", ar["current_level"] == 1 and ar["total_xp"] == 0 and ar["total_records"] == 0, str(ar))
check("等级规则: xp_to_next_level=100", ar["xp_to_next_level"] == 100, str(ar))

print("== 8. 写入学习记录并验证分页/统计 ==")
with ds.SessionLocal() as s:
    from app.models.learning import LearningRecord
    s.add_all([
        LearningRecord(user_id=uid, module_type="course", action_type="start", duration=30, result={"chapter": 1}),
        LearningRecord(user_id=uid, module_type="course", action_type="finish", duration=900, result={"score": 80}),
        LearningRecord(user_id=uid, module_type="exercise", action_type="submit", duration=120, result={"correct": 5, "total": 8}),
    ])
    s.commit()

r = client.get("/api/v1/users/learning-records", headers=h, params={"page": 1, "page_size": 2})
recs = r.json()["data"]
check("记录分页 total=3", recs["total"] == 3, str(recs))
check("page_size=2 生效", len(recs["items"]) == 2)
r = client.get("/api/v1/users/learning-records", headers=h, params={"module_type": "course", "page_size": 10})
recs = r.json()["data"]
check("按模块筛选 total=2", recs["total"] == 2, str(recs))

r = client.get("/api/v1/users/learning-archive", headers=h)
ar = r.json()["data"]
check("统计: 记录数3/时长1050/完成1", ar["total_records"] == 3 and ar["total_duration"] == 1050 and ar["finished_count"] == 1, str(ar))

print("== 9. 写入测评报告并验证分页 ==")
with ds.SessionLocal() as s:
    from app.models.assessment import AssessmentReport
    s.add_all([
        AssessmentReport(user_id=uid, assessment_id=1, report_type="career",
                         report_json={"persona_tags": ["逻辑型"], "summary": "画像测试"}),
        AssessmentReport(user_id=uid, assessment_id=2, report_type="stage",
                         report_json={"summary": "阶段复盘"}),
    ])
    s.commit()

r = client.get("/api/v1/users/assessment-reports", headers=h, params={"page_size": 10})
reps = r.json()["data"]
check("报告 total=2", reps["total"] == 2, str(reps))
r = client.get("/api/v1/users/assessment-reports", headers=h, params={"report_type": "career"})
reps = r.json()["data"]
check("报告按类型筛选 total=1", reps["total"] == 1 and reps["items"][0]["report_json"]["persona_tags"] == ["逻辑型"])

print("== 10. 等级规则引擎 ==")
from app.api.v1.endpoints.users import level_from_xp, xp_to_next_level
check("xp=500 -> level=3", level_from_xp(500) == 3, str(level_from_xp(500)))
check("level3: xp_to_next=300", xp_to_next_level(300, 3) == 300, str(xp_to_next_level(300, 3)))

print(f"\n结果: PASS={PASS} FAIL={FAIL}")
raise SystemExit(1 if FAIL else 0)