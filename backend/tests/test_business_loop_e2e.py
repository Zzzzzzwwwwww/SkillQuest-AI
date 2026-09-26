"""
模块8 六大业务闭环 —— 端到端验证脚本

闭环1 注册即建档案 → 闭环2 测评后自动画像+推荐岗位 → 闭环3 选定岗位自动生成图谱/路径 →
闭环4 阶段测评联动掌握度+弱点诊断 → 闭环5 弱点推送 AI 导师 → 闭环6 Boss 挑战发放 XP/升级技能等级。

原则（第1条）：画像/路径/评分/奖励/等级/技能状态全部规则计算。
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
# 0. 准备：注册 + 全量种子（测评/技能图谱/资源/阶段测评）
# ------------------------------------------------------------------- #
print("== 0. 准备：注册 + 种子 ==")
suffix = str(random.randint(1000, 9999))
username = f"loop_{suffix}"
r = client.post("/api/v1/auth/register", json={
    "username": username,
    "email": f"{username}@example.com",
    "password": "pass1234",
})
check("注册返回200", r.status_code == 200, r.text)
uid = r.json()["data"]["user"]["id"]
h = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}

from app.db.seed_assessment import seed_assessment, count_questions  # noqa: E402
from app.db.seed_skill import seed_skill  # noqa: E402
from app.db.seed_learning import seed_learning_resources  # noqa: E402
from app.db.seed_exam import seed_exams  # noqa: E402
from sqlalchemy import select  # noqa: E402
from app.models.skill import SkillNode  # noqa: E402

with ds.SessionLocal() as s:
    paper = seed_assessment(s)
    seed_skill(s)
    seed_learning_resources(s)
    seed_exams(s)
    s.commit()
    paper_id = paper.id
assert count_questions(ds.SessionLocal(), title="职业发展综合测评 V1") == 12

# ------------------------------------------------------------------- #
# 1. 闭环1：注册后自动创建学习档案
# ------------------------------------------------------------------- #
print("== 1. 闭环1：注册即建档案 ==")
r = client.get("/api/v1/users/learning-archive", headers=h)
check("学习档案已自动创建", r.status_code == 200 and r.json()["data"] is not None, r.text)
arch1 = r.json()["data"]
check("初始等级=1 XP=0", arch1["current_level"] == 1 and arch1["total_xp"] == 0, str(arch1))
r = client.get("/api/v1/users/me", headers=h)
check("个人资料已自动初始化", r.json()["data"]["profile"] is not None)

# ------------------------------------------------------------------- #
# 2. 闭环2：完成职业测评 → 自动生成画像 + 推荐岗位
# ------------------------------------------------------------------- #
print("== 2. 闭环2：测评后自动画像 ==")
r = client.get("/api/v1/assessment/questions", headers=h, params={"paper_id": paper_id})
qs = r.json()["data"]
high_answers = [
    {"question_id": qs[0]["id"], "answer": "C"},   # logic
    {"question_id": qs[1]["id"], "answer": 5},     # programming
    {"question_id": qs[2]["id"], "answer": 5},     # data
    {"question_id": qs[3]["id"], "answer": 3},     # spatial
    {"question_id": qs[4]["id"], "answer": "A"},   # language
    {"question_id": qs[5]["id"], "answer": 4},     # hands_on
    {"question_id": qs[6]["id"], "answer": ["A", "B", "C"]},
    {"question_id": qs[7]["id"], "answer": "A"},
    {"question_id": qs[8]["id"], "answer": ["B", "D"]},
    {"question_id": qs[9]["id"], "answer": "希望成为 AI 算法工程师，因为喜欢用数据解决智能问题"},
    {"question_id": qs[10]["id"], "answer": "夯实算法与编程基础，系统学习机器学习"},
    {"question_id": qs[11]["id"], "answer": "成为能独立落地 AI 应用的工程师"},
]
r = client.post("/api/v1/assessment/submit", json={"paper_id": paper_id, "answers": high_answers, "duration": 180}, headers=h)
check("测评提交成功", r.status_code == 200, r.text)
check("返回推荐 Top 岗位", bool(r.json()["data"]["top_job"]), r.text)

r = client.get("/api/v1/persona/current", headers=h)
check("画像已自动生成", r.status_code == 200 and r.json()["data"] is not None, r.text)
persona = r.json()["data"]
check("画像含目标岗位", bool(persona["target_job"]), str(persona.get("target_job")))
check("画像含雷达", len(persona["ability_radar"]["dimensions"]) > 0)

r = client.get("/api/v1/users/learning-archive", headers=h)
check("目标岗位已回写学习档案", r.json()["data"]["target_job"] == persona["target_job"], str(r.json()["data"]))

# ------------------------------------------------------------------- #
# 3. 闭环3：选定岗位 → 自动生成技能图谱 + 学习路径
# ------------------------------------------------------------------- #
print("== 3. 闭环3：选定岗位自动生成路径 ==")
r = client.get("/api/v1/jobs", headers=h)
jobs = r.json()["data"]
job = next((j for j in jobs if j["job_name"] == "AI 应用开发工程师"), jobs[0])
r = client.post("/api/v1/jobs/select", json={"job_id": job["id"], "auto_generate_path": True}, headers=h)
check("选定岗位成功", r.status_code == 200, r.text)
sel = r.json()["data"]
check("自动生成路径标记", sel["auto_generated_path"] is True and sel["path"] is not None, str(sel.get("meta")))
check("路径段位齐全", len(sel["path"]["stage_order"]) >= 4, str(sel["path"].get("stage_order")))
r = client.get("/api/v1/learning-path/current", headers=h)
check("当前路径已生成", r.status_code == 200 and r.json()["data"] is not None, r.text)
r = client.get("/api/v1/persona/current", headers=h)
check("画像目标岗位已切换", r.json()["data"]["target_job"] == job["job_name"], str(r.json()["data"]["target_job"]))

# ------------------------------------------------------------------- #
# 4. 闭环4：阶段测评 → 掌握度联动 + 弱点诊断落库
# ------------------------------------------------------------------- #
print("== 4. 闭环4：阶段测评联动 ==")
with ds.SessionLocal() as s:
    from app.models.assessment_review import StageExam
    bronze = s.scalar(select(StageExam).where(StageExam.stage == "bronze"))
    bronze_id = bronze.id

r = client.post("/api/v1/exam/start", json={"exam_id": bronze_id}, headers=h)
start = r.json()["data"]
record_id = start["record_id"]
qlist = start["questions"]
ans = []
for i, q in enumerate(qlist):
    t = q["question_type"]
    if t == "single":
        ua = "C" if i == 3 else "A"
    elif t == "multiple":
        ua = ["A", "B", "C"]
    else:
        ua = False
    ans.append({"question_id": q["id"], "user_answer": ua})
r = client.post("/api/v1/exam/submit", json={"record_id": record_id, "answers": ans}, headers=h)
check("阶段测评提交成功", r.status_code == 200, r.text)
check("规则得分=80", r.json()["data"]["score"] == 80, r.text)

r = client.get(f"/api/v1/users/{uid}/skill-status", headers=h)
check("掌握度联动技能状态", r.status_code == 200, r.text)
sks = r.json()["data"]["items"]
kp_rows = [it for it in sks if it["mastery_score"] >= 0]
check("技能状态有写入", len(kp_rows) > 0, str(sks)[:200])

r = client.get("/api/v1/chat/weaknesses", headers=h)
check("弱点诊断已落库", r.status_code == 200 and len(r.json()["data"]) >= 1, r.text)
weak = r.json()["data"][0]
check("弱点含排序与查找且带建议", weak["kp_name"] == "排序与查找" and bool(weak["diagnosis"]), str(weak))

r = client.get("/api/v1/users/learning-records", headers=h)
check("学习记录含阶段测评打点", any(it["module_type"] == "assessment" for it in r.json()["data"]["items"]), str(r.json()["data"])[:200])

# 闭环5：弱点上下文注入（单元级）
from app.services.rag import build_learning_context  # noqa: E402
with ds.SessionLocal() as s:
    ctx = build_learning_context(s, uid)
check("导师上下文含弱点", "待攻克弱点" in ctx and "排序与查找" in ctx, ctx[:120])
check("导师上下文含路径信息", "目标岗位" in ctx, ctx[:80])
r = client.post("/api/v1/chat/session", json={"title": "弱点攻克"}, headers=h)
sid = r.json()["data"]["id"]
r = client.post("/api/v1/chat/message", json={"session_id": sid, "content": "如何攻克排序与查找这个弱点？"}, headers=h)
check("导师会话可发起(SSE 200)", r.status_code == 200, str(r.status_code))

# ------------------------------------------------------------------- #
# 5. 闭环6：Boss 挑战 → XP/等级/技能等级自动更新
# ------------------------------------------------------------------- #
print("== 5. 闭环6：Boss 挑战 ==")
with ds.SessionLocal() as s:
    skill = s.scalar(select(SkillNode).where(SkillNode.node_type == "skill"))
    assert skill is not None, "技能节点缺失"
    skill_id = skill.id
    skill_name = skill.name
r = client.post("/api/v1/boss/start", json={"skill_node_id": skill_id}, headers=h)
check("Boss 挑战开始", r.status_code == 200, r.text)
bz = r.json()["data"]
check("下发题目>=3", len(bz["questions"]) >= 3, str(len(bz["questions"])))
check("不下发答案", all("answer" not in q for q in bz["questions"]))

from app.models.assessment_review import ExamQuestion  # noqa: E402
with ds.SessionLocal() as s:
    answers_true = []
    for q in bz["questions"]:
        row = s.get(ExamQuestion, q["id"])
        answers_true.append({"question_id": q["id"], "user_answer": row.answer})
r = client.post("/api/v1/boss/finish", json={"skill_node_id": skill_id, "answers": answers_true}, headers=h)
check("Boss 挑战完成", r.status_code == 200, r.text)
fin = r.json()["data"]
check("满分通过", fin["pass_flag"] is True and fin["score"] == 100, str(fin))
check("发放 XP>0", fin["reward_xp"] > 0, str(fin))

r = client.get("/api/v1/users/learning-archive", headers=h)
arch2 = r.json()["data"]
# 累计 XP = Boss 奖励 + 一次 AI 导师答疑(+5, 模块9 规则)
check("总 XP 已累计", arch2["total_xp"] == fin["reward_xp"] + 5, str(arch2))
check("等级已同步", arch2["current_level"] == fin["level"], str(arch2))

r = client.get(f"/api/v1/users/{uid}/skill-status", headers=h)
skill_rows = [it for it in r.json()["data"]["items"] if it["skill_node_id"] == skill_id]
check("技能等级已更新", skill_rows and skill_rows[0]["mastery_score"] >= 80 and skill_rows[0]["status"] == "mastered", str(skill_rows))

r = client.get("/api/v1/users/learning-records", headers=h)
check("学习记录含 boss 挑战", any(it["module_type"] == "boss" for it in r.json()["data"]["items"]), str(r.json()["data"])[:200])

# 失败路径：故意全错
r = client.post("/api/v1/boss/start", json={"skill_node_id": skill_id}, headers=h)
bz2 = r.json()["data"]
with ds.SessionLocal() as s:
    answers_wrong = []
    for q in bz2["questions"]:
        row = s.get(ExamQuestion, q["id"])
        correct = row.answer
        if isinstance(correct, list):
            ua = [x for x in ["A", "B", "C", "D"] if x not in correct][:1]
        elif isinstance(correct, bool):
            ua = not correct
        else:
            opts = [o["key"] for o in (row.options_json or [])]
            ua = next((x for x in opts if x != correct), "Z")
        answers_wrong.append({"question_id": q["id"], "user_answer": ua})
r = client.post("/api/v1/boss/finish", json={"skill_node_id": skill_id, "answers": answers_wrong}, headers=h)
check("失败路径不通过", r.status_code == 200 and r.json()["data"]["pass_flag"] is False, r.text)

# ------------------------------------------------------------------- #
print()
print(f"业务闭环 E2E: PASS={PASS} FAIL={FAIL}")
raise SystemExit(1 if FAIL else 0)