"""
模块4 岗位技能图谱 —— 端到端验证脚本

流程：注册 → 种子岗位/技能 → 岗位列表 → 技能树(结构/状态标注) →
      用户技能状态 GET/PUT（状态推导）→ 技能详情(前置知识/资源/关联岗位) →
      Skill Gap 分析（掌握度/匹配度/差距）。

掌握状态、掌握度、Gap 全部规则计算。
"""

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
# 0. 准备
# ------------------------------------------------------------------- #
print("== 0. 准备：注册 + 种子技能图谱 ==")
r = client.post("/api/v1/auth/register", json={
    "username": "mapper", "email": "mapper@example.com", "password": "secret123",
})
body = r.json()
token = body["data"]["access_token"]
uid = body["data"]["user"]["id"]
h = {"Authorization": f"Bearer {token}"}

with ds.SessionLocal() as s:
    from app.db.seed_skill import seed_skill
    stat = seed_skill(s)
    s.commit()
print("  种子统计:", stat)
check("种子岗位6个", stat["jobs"] == 6, str(stat))
check("种子能力域6个", stat["capabilities"] == 6, str(stat))
check("种子技能15个", stat["skills"] == 15, str(stat))

# ------------------------------------------------------------------- #
# 1. 岗位列表
# ------------------------------------------------------------------- #
print("== 1. GET /jobs ==")
r = client.get("/api/v1/jobs", headers=h)
check("jobs 200", r.status_code == 200)
jobs = r.json()["data"]
check("岗位数量=6", len(jobs) == 6, str(len(jobs)))
check("岗位含技能数", jobs[0]["skill_count"] >= 3, str(jobs[0]))
check("含岗位族字段", all("job_family" in j and j["job_family"] for j in jobs))
r = client.get("/api/v1/jobs", headers=h, params={"family": "产品设计"})
check("按岗位族筛选=2", len(r.json()["data"]) == 2, str(len(r.json()["data"])))
check("无token 401", client.get("/api/v1/jobs").status_code == 401)
ai_job = next(j for j in jobs if j["job_name"] == "AI 应用开发工程师")
backend_job = next(j for j in jobs if j["job_name"] == "后端工程师")

# ------------------------------------------------------------------- #
# 2. 技能树
# ------------------------------------------------------------------- #
print("== 2. GET /jobs/{id}/skill-tree ==")
r = client.get(f"/api/v1/jobs/{ai_job['id']}/skill-tree", headers=h)
check("skill-tree 200", r.status_code == 200, str(r.status_code))
data = r.json()["data"]
tree = data["tree"]
check("树根=岗位", tree["node_type"] == "job" and tree["name"] == "AI 应用开发工程师")
check("根下能力域>=4", len(tree["children"]) >= 4, str([c["name"] for c in tree["children"]]))
locomotive = next(c for c in tree["children"] if c["name"] == "编程基础")
check("能力域名正确", locomotive["node_type"] == "capability")
skill_children = locomotive["children"]
check("能力域下有技能", len(skill_children) >= 3, str([s["name"] for s in skill_children]))
py = next(s for s in skill_children if s["name"] == "Python 基础")
check("技能带岗位要求", py["required_level"] == 80 and py["importance"] == 95, str(py))
check("技能下知识点>=3", len(py["children"]) >= 3 and py["children"][0]["node_type"] == "knowledge")
check("默认状态未掌握", py["status"] == "not_started" and py["mastery_score"] == 0)
check("技能带前置知识", isinstance(py["prerequisites"], list))

# 汇总字段
summary = data["summary"]
check("Gap汇总含字段", {"overall_mastery", "fit_rate", "skill_count", "mastered_count", "gaps"} <= set(summary.keys()))
check("岗位要求技能数=11", summary["skill_count"] == 11, str(summary["skill_count"]))
check("初始掌握度0", summary["overall_mastery"] == 0 and summary["fit_rate"] == 0)
r = client.get("/api/v1/jobs/99999/skill-tree", headers=h)
check("岗位不存在404", r.status_code == 404)

# ------------------------------------------------------------------- #
# 3. 用户技能状态读写
# ------------------------------------------------------------------- #
print("== 3. GET/PUT /users .../skill-status ==")
r = client.get(f"/api/v1/users/{uid}/skill-status", headers=h)
check("初始状态 total=0", r.json()["data"]["total"] == 0)

# 拿到 python 技能节点 id
with ds.SessionLocal() as s:
    from app.models.skill import SkillNode
    py_row = s.execute(
        s.query(SkillNode).filter(SkillNode.name == "Python 基础")
    ).first()
    py_id = py_row[0].id
    web_row = s.execute(
        s.query(SkillNode).filter(SkillNode.name == "Web 全栈开发")
    ).first()
    web_id = web_row[0].id
    ml_row = s.execute(
        s.query(SkillNode).filter(SkillNode.name == "机器学习基础")
    ).first()
    ml_id = ml_row[0].id

r = client.get(f"/api/v1/users/{uid + 999}/skill-status", headers=h)
check("他人技能状态403", r.status_code == 403)

# 更新：Python mastered(90) / Web learning(40) / 机器学习 not_started(0 显式)
r = client.put("/api/v1/users/skill-status", headers=h, json={
    "items": [
        {"skill_node_id": py_id, "mastery_score": 90, "status": "mastered"},
        {"skill_node_id": web_id, "mastery_score": 40},
        {"skill_node_id": ml_id, "mastery_score": 0, "status": "not_started"},
    ]
})
check("PUT 200", r.status_code == 200, str(r.status_code) + str(r.text))
items = r.json()["data"]["items"]
check("同步后 total=3", len(items) == 3, str(items))
mapping = {i["skill_node_id"]: i for i in items}
check("显式状态已掌握生效", mapping[py_id]["status"] == "mastered")
check("缺省状态按掌握度推导(learning)", mapping[web_id]["status"] == "learning", str(mapping[web_id]))
check("缺省状态推导(not_started)", mapping[ml_id]["status"] == "not_started")

r = client.put("/api/v1/users/skill-status", headers=h, json={
    "items": [{"skill_node_id": 99999999, "mastery_score": 50}]
})
check("不存在的节点400", r.status_code == 400)

# ------------------------------------------------------------------- #
# 4. 技能树叠加掌握状态 + Gap 重算
# ------------------------------------------------------------------- #
print("== 4. 状态叠加与 Gap 分析 ==")
r = client.get(f"/api/v1/jobs/{ai_job['id']}/skill-tree", headers=h)
tree = r.json()["data"]["tree"]
py = next(
    s
    for c in tree["children"]
    if c["name"] == "编程基础"
    for s in c["children"]
    if s["name"] == "Python 基础"
)
check("树节点状态已叠加", py["status"] == "mastered" and py["mastery_score"] == 90, str(py))

gaps = r.json()["data"]["summary"]["gaps"]
py_gap = next(g for g in gaps if g["name"] == "Python 基础")
check("已达标技能 gap=0", py_gap["gap"] == 0 and py_gap["mastery"] == 90, str(py_gap))
web_gap = next(g for g in gaps if g["name"] == "Web 全栈开发")
check("学习中技能 gap=35", web_gap["gap"] == 35, str(web_gap))
check("overall_mastery>0", r.json()["data"]["summary"]["overall_mastery"] > 0)
check("fit_rate<100", r.json()["data"]["summary"]["fit_rate"] < 100)

r = client.get(f"/api/v1/jobs/{backend_job['id']}/skill-tree", headers=h)
check("后端岗位技能数=6", r.json()["data"]["summary"]["skill_count"] == 6, str(r.json()["data"]["summary"]))

# ------------------------------------------------------------------- #
# 5. 技能详情
# ------------------------------------------------------------------- #
print("== 5. GET /skills/{id}/detail ==")
r = client.get(f"/api/v1/skills/{py_id}/detail", headers=h)
check("detail 200", r.status_code == 200)
d = r.json()["data"]
check("详情基本字段", d["name"] == "Python 基础" and d["node_type"] == "skill" and d["level"] == 2)
check("掌握度同步", d["mastery_score"] == 90 and d["status"] == "mastered")
check("推荐资源3条", len(d["resources"]) == 3 and all("title" in res for res in d["resources"]))
check("关联岗位>=1", len(d["related_jobs"]) >= 1 and d["related_jobs"][0]["required_level"] == 80)
check("前置知识列表存在", isinstance(d["prerequisites"], list))

# 依赖性的前置知识（雪花：数据结构与算法 前置 Python 基础）
with ds.SessionLocal() as s:
    from app.models.skill import SkillNode
    algo = s.scalar(s.query(SkillNode).filter(SkillNode.name == "数据结构与算法"))
    algo_id = algo.id
r = client.get(f"/api/v1/skills/{algo_id}/detail", headers=h)
d = r.json()["data"]
check("前置知识含 Python 基础", any(p["name"] == "Python 基础" for p in d["prerequisites"]), str(d["prerequisites"]))
check("前置知识带掌握状态", any(p["name"] == "Python 基础" and p["status"] == "mastered" for p in d["prerequisites"]))
r = client.get("/api/v1/skills/99999/detail", headers=h)
check("技能不存在404", r.status_code == 404)

# ------------------------------------------------------------------- #
# 6. 状态规则单测
# ------------------------------------------------------------------- #
print("== 6. 状态规则单测 ==")
from app.services.skill_tree import infer_status, normalize_status  # noqa: E402
from app.models.skill import STATUS_MASTERED, STATUS_LEARNING, STATUS_NOT_STARTED  # noqa: E402
check("80>=mastered", infer_status(80) == STATUS_MASTERED)
check("79=learning", infer_status(79) == STATUS_LEARNING)
check("1=learning", infer_status(1) == STATUS_LEARNING)
check("0=not_started", infer_status(0) == STATUS_NOT_STARTED)
check("显式状态覆盖推导", normalize_status(STATUS_LEARNING, 95) == STATUS_LEARNING)
check("缺省状态推导", normalize_status(None, 95) == STATUS_MASTERED)

print(f"\n结果: PASS={PASS} FAIL={FAIL}")
raise SystemExit(1 if FAIL else 0)