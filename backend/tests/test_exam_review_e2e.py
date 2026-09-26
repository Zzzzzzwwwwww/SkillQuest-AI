"""
模块7 学习评估复盘 —— 端到端验证脚本

流程：注册 → 种子技能图谱/学习资源/阶段测评试卷 → 开始测评(下发题目不含答案) →
      提交答卷(规则评分) → 结果详情(分数/对错/掌握度/雷达/趋势/薄弱/下一步) →
      掌握度总览(热力图) → 生成学习报告(规则模板) → 历史列表 → 报告详情 →
      PDF 导出(application/pdf) → 越权/404/重复提交防守。

原则（第1条）：总分/掌握度/薄弱识别全部规则计算，AI 仅报告增强(未配置时降级)。
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


def register(name_suffix: str):
    suffix = str(random.randint(1000, 9999))
    username = f"exam_{name_suffix}_{suffix}"
    r = client.post("/api/v1/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "pass1234",
    })
    assert r.status_code == 200, r.text
    token = r.json()["data"]["access_token"]
    uid = r.json()["data"]["user"]["id"]
    return username, token, uid


# ------------------------------------------------------------------- #
# 0. 准备：注册两名用户 + 种子技能图谱/学习资源/阶段测评
# ------------------------------------------------------------------- #
print("== 0. 准备：注册 + 种子数据 ==")
_, token_a, uid_a = register("a")
_, token_b, uid_b = register("b")
ha = {"Authorization": f"Bearer {token_a}"}
hb = {"Authorization": f"Bearer {token_b}"}

from app.db.seed_skill import seed_skill  # noqa: E402
from app.db.seed_learning import seed_learning_resources  # noqa: E402
from app.db.seed_exam import seed_exams  # noqa: E402
from sqlalchemy import select  # noqa: E402
from app.models.assessment_review import StageExam, ExamQuestion  # noqa: E402

with ds.SessionLocal() as s:
    stats = seed_skill(s)
    s.commit()
check("种子技能图谱", stats["jobs"] == 6 and stats["knowledges"] == 45, str(stats))

with ds.SessionLocal() as s:
    rsrc = seed_learning_resources(s)
    s.commit()
check("种子学习资源", rsrc["resources"] == 240, str(rsrc))

with ds.SessionLocal() as s:
    exam_stats = seed_exams(s)
    s.commit()
check("种子阶段测评(2套x5题)", exam_stats["exams"] == 2 and exam_stats["questions"] == 10, str(exam_stats))

with ds.SessionLocal() as s:
    bronze = s.scalar(select(StageExam).where(StageExam.stage == "bronze"))
    silver = s.scalar(select(StageExam).where(StageExam.stage == "silver"))
    bronze_id = bronze.id
    silver_id = silver.id
check("青铜试卷存在", bronze is not None and bronze.total_score == 100, str(bronze_id if bronze else None))

# ------------------------------------------------------------------- #
# 1. 开始测评：下发题目但不下发答案
# ------------------------------------------------------------------- #
print("== 1. 开始测评 ==")
r = client.post("/api/exam/start", json={"exam_id": bronze_id}, headers=ha)
check("开始测评成功", r.status_code == 200, r.text)
start = r.json()["data"]
check("下发题目数=5", len(start["questions"]) == 5, str(len(start["questions"])))
check("不下发正确答案", all("correct_answer" not in q and "answer" not in q for q in start["questions"]))
record_id = start["record_id"]
qlist = start["questions"]

# 未登录访问
r = client.post("/api/exam/start", json={"exam_id": bronze_id})
check("未登录返回401", r.status_code == 401, str(r.status_code))

# ------------------------------------------------------------------- #
# 2. 提交答卷：第 4 题故意答错，期望 score=80，correct=4
# ------------------------------------------------------------------- #
print("== 2. 提交答卷(规则评分) ==")
answers = []
for i, q in enumerate(qlist):
    t = q["question_type"]
    if t == "single":
        ua = "C" if i == 3 else "A"  # 第4题(二分查找)故意答错
    elif t == "multiple":
        ua = ["A", "B", "C"]
    else:  # judge
        ua = False
    answers.append({"question_id": q["id"], "user_answer": ua})

r = client.post("/api/exam/submit", json={"record_id": record_id, "answers": answers}, headers=ha)
check("提交成功", r.status_code == 200, r.text)
sub = r.json()["data"]
check("得分=80(满分100错一题)", sub["score"] == 80, str(sub))
check("答对数=4/5", sub["correct_count"] == 4 and sub["total_count"] == 5, str(sub))
check("及格判定 pass_flag=true", sub["pass_flag"] is True, str(sub))

# 重复提交被拒
r = client.post("/api/exam/submit", json={"record_id": record_id, "answers": answers}, headers=ha)
check("重复提交返回400", r.status_code == 400, r.text)

# ------------------------------------------------------------------- #
# 3. 结果详情：分数/对错/掌握度/雷达/趋势/薄弱/下一步
# ------------------------------------------------------------------- #
print("== 3. 测评结果详情 ==")
r = client.get(f"/api/v1/exam/result/{record_id}", headers=ha)
check("结果详情成功", r.status_code == 200, r.text)
res = r.json()["data"]
check("结果分数=80", res["score"] == 80, str(res["score"]))
check("题目对错明细(错1题=4对)", sum(1 for q in res["questions"] if q["is_correct"]) == 4, str(res["questions"]))
check("掌握度非空", len(res["mastery"]) >= 4, str(res["mastery"]))
check("雷达图聚合", len(res["radar"]) >= 1 and all("domain" in p and "value" in p for p in res["radar"]), str(res["radar"]))
check("学习趋势含本次", len(res["trend"]) == 1 and res["trend"][0]["score"] == 80, str(res["trend"]))
weak = res["weak_points"]
check("薄弱点识别(排序与查找=0)", any(w["name"] == "排序与查找" and w["mastery_score"] == 0 for w in weak), str(weak))
check("薄弱点带建议", all(w["suggestion"] for w in weak), str(weak))
check("下一步推荐非空", len(res["next_steps"]) >= 1, str(res["next_steps"]))

# 无权限越权读取
r = client.get(f"/api/v1/exam/result/{record_id}", headers=hb)
check("他人记录返回404", r.status_code == 404, str(r.status_code))

# ------------------------------------------------------------------- #
# 4. 掌握度总览（热力图）
# ------------------------------------------------------------------- #
print("== 4. 掌握度总览 ==")
r = client.get("/api/mastery", headers=ha)
check("掌握度总览成功", r.status_code == 200, r.text)
m = r.json()["data"]
check("掌握度条目>=4", len(m["items"]) >= 4, str(m["items"]))
check("热力图结构(domains+points)", "domains" in m["heatmap"] and "points" in m["heatmap"], str(m["heatmap"]))
zero_kp = [it for it in m["items"] if it["name"] == "排序与查找"]
check("排序与查找掌握度=0", zero_kp and zero_kp[0]["mastery_score"] == 0, str(zero_kp))

# ------------------------------------------------------------------- #
# 5. 学习报告：生成 → 列表 → 详情
# ------------------------------------------------------------------- #
print("== 5. 学习报告 ==")
r = client.post("/api/v1/report/generate", json={"record_id": record_id, "report_type": "exam_review"}, headers=ha)
check("报告生成成功", r.status_code == 200, r.text)
rep = r.json()["data"]
rj = rep["report_json"]
check("报告含总体评价", bool(rj.get("overall")), str(rj.get("overall")))
check("报告含优势列表", isinstance(rj.get("strengths"), list) and len(rj["strengths"]) >= 3, str(rj.get("strengths")))
check("报告含薄弱建议与下一步", rj.get("suggestion") and rj.get("next_steps"), str(rj))
check("报告含雷达/趋势", rj.get("radar") and rj.get("trend"), str(rj))
rep_id = rep["id"]

r = client.post("/api/report/generate", json={}, headers=ha)
check("缺省record_id生成最新报告", r.status_code == 200 and r.json()["data"]["id"] > 0, r.text)

r = client.get("/api/report/list", headers=ha)
check("报告列表 >=2 条", r.status_code == 200 and len(r.json()["data"]) >= 2, r.text)

r = client.get(f"/api/v1/report/{rep_id}", headers=ha)
check("报告详情一致", r.status_code == 200 and r.json()["data"]["id"] == rep_id, r.text)

# 越权读报告
r = client.get(f"/api/v1/report/{rep_id}", headers=hb)
check("他人报告返回404", r.status_code == 404, str(r.status_code))

# ------------------------------------------------------------------- #
# 6. PDF 导出
# ------------------------------------------------------------------- #
print("== 6. PDF 导出 ==")
r = client.get(f"/api/report/export/pdf?report_id={rep_id}", headers=ha)
check("PDF 导出成功", r.status_code == 200, r.text)
check("Content-Type=application/pdf", r.headers.get("content-type", "").startswith("application/pdf"), r.headers.get("content-type", ""))
check("PDF 内容非空且含%PDF头", len(r.content) > 200 and r.content[:4] == b"%PDF", f"len={len(r.content)}")

r = client.get(f"/api/report/export/pdf?report_id={rep_id}", headers=hb)
check("越权导出返回404", r.status_code == 404, str(r.status_code))

# ------------------------------------------------------------------- #
# 7. 防守与不存在场景
# ------------------------------------------------------------------- #
print("== 7. 边界与防守 ==")
r = client.post("/api/exam/start", json={"exam_id": 99999}, headers=ha)
check("不存在试卷返回404", r.status_code == 404, str(r.status_code))

r = client.get(f"/api/v1/exam/result/{99999}", headers=ha)
check("不存在测评记录返回404", r.status_code == 404, str(r.status_code))

r = client.post("/api/report/generate", json={"record_id": 99999}, headers=ha)
check("不存在记录生成报告返回400", r.status_code == 400, str(r.status_code))

# 用户B也做一次：走 silver 试卷（覆盖第二种试卷）
r = client.post("/api/exam/start", json={"exam_id": silver_id}, headers=hb)
check("B用户开始白银测评", r.status_code == 200, r.text)
rec_b = r.json()["data"]["record_id"]
qb = r.json()["data"]["questions"]
ab = [{"question_id": q["id"], "user_answer": ("A" if q["question_type"] == "single" else (["A", "B", "C"] if q["question_type"] == "multiple" else True))} for q in qb]
r = client.post("/api/exam/submit", json={"record_id": rec_b, "answers": ab}, headers=hb)
check("B用户提交成功", r.status_code == 200, r.text)
with ds.SessionLocal() as s:
    q_with_agent = s.get(ExamQuestion, qb[3]["id"])
check("试卷2题目有正确答案(入库)", q_with_agent.answer is not None, str(q_with_agent.answer))

# ------------------------------------------------------------------- #
print()
print(f"学习评估复盘 E2E: PASS={PASS} FAIL={FAIL}")
raise SystemExit(1 if FAIL else 0)