"""
模块3 职业测评与画像 —— 端到端验证脚本

流程：注册 → 种子试卷 → 试卷列表 → 取题(不含评分规则) → 提交答卷 →
      返回结果(总分/雷达图/Top3岗位/技能差距) → 生成画像 → 复核画像。

评分、推荐全部规则计算；本环境未配置 LLM，画像增强走规则降级。
"""

import warnings

warnings.filterwarnings("ignore")

# SQLite 替身兼容：BigInteger 主键编译为 INTEGER 以获得自增长
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
# 0. 准备：注册用户 + 种子试卷
# ------------------------------------------------------------------- #
print("== 0. 准备：注册 + 种子试卷 ==")
r = client.post("/api/v1/auth/register", json={
    "username": "seeker", "email": "seeker@example.com", "password": "secret123",
})
check("注册返回200", r.status_code == 200, str(r.status_code))
body = r.json()
token = body["data"]["access_token"]
uid = body["data"]["user"]["id"]
h = {"Authorization": f"Bearer {token}"}

with ds.SessionLocal() as s:
    from app.db.seed_assessment import seed_assessment, count_questions
    paper = seed_assessment(s)
    s.commit()
    paper_id = paper.id
q_count = count_questions(ds.SessionLocal(), title="职业发展综合测评 V1")
check("种子试卷含12题", q_count == 12, str(q_count))

# ------------------------------------------------------------------- #
# 1. 试卷列表
# ------------------------------------------------------------------- #
print("== 1. GET /assessment/papers ==")
r = client.get("/api/v1/assessment/papers", headers=h)
check("papers 200", r.status_code == 200)
papers = r.json()["data"]
check("活性试卷=1", len(papers) == 1, str(papers))
check("试卷含题目数", papers[0]["question_count"] == 12, str(papers[0]))
check("无token 401", client.get("/api/v1/assessment/papers").status_code == 401)

# ------------------------------------------------------------------- #
# 2. 取题
# ------------------------------------------------------------------- #
print("== 2. GET /assessment/questions ==")
r = client.get("/api/v1/assessment/questions", headers=h, params={"paper_id": paper_id})
check("questions 200", r.status_code == 200)
qs = r.json()["data"]
check("题目数量=12", len(qs) == 12, str(len(qs)))
check("不下发评分规则", all("score_rule" not in q for q in qs))
check("含中文维度标签", all("dimension_label" in q and q["dimension_label"] for q in qs))
first = qs[0]
check("单选含options", first["question_type"] == "single" and len(first["options"]) == 4)
scale_q = next(q for q in qs if q["question_type"] == "scale")
check("量表含scale参数", scale_q["scale"]["min"] == 1 and scale_q["scale"]["max"] == 5)
text_q = next(q for q in qs if q["question_type"] == "text")
check("简答含placeholder", bool(text_q["placeholder"]))
r = client.get("/api/v1/assessment/questions", headers=h, params={"paper_id": 99999})
check("试卷不存在404", r.status_code == 404)

# ------------------------------------------------------------------- #
# 3. 评分规则引擎单测
# ------------------------------------------------------------------- #
print("== 3. 评分规则引擎 ==")
from app.models.assessment import AssessmentQuestion
from app.services.assessment_scoring import score_question, _to_score


def qobj(qtype, rule, options):
    return AssessmentQuestion(
        id=1, paper_id=1, question_type=qtype, content="x", dimension="logic",
        options_json=options, score_rule=rule, order_no=1,
    )

check("单选取映射分", _to_score(score_question(qobj("single", {"type": "direct", "values": {"A": 100, "B": 50}}, {"A": "a", "B": "b"}), "A")) == 100.0)
check("单选未知项记0", _to_score(score_question(qobj("single", {"type": "direct", "values": {"A": 100}}, {"A": "a"}), "Z")) == 0.0)
check("多选求和封顶", _to_score(score_question(qobj("multiple", {"type": "sum", "values": {"A": 60, "B": 60}, "max": 100}, {"A": "a", "B": "b"}), ["A", "B"])) == 100.0)
check("多选单项", _to_score(score_question(qobj("multiple", {"type": "sum", "values": {"A": 60, "B": 60}, "max": 100}, {"A": "a", "B": "b"}), ["A"])) == 60.0)
check("量表线性映射", _to_score(score_question(qobj("scale", {"type": "scale", "min": 1, "max": 5}, {"1": "一"}), 3)) == 50.0)
check("量表边界", _to_score(score_question(qobj("scale", {"type": "scale", "min": 1, "max": 5}, {"5": "五"}), 5)) == 100.0)
check("简答关键词+长度", _to_score(score_question(qobj("text", {"type": "text", "keywords": ["编程"], "min_len": 10, "base": 40}, None), "我每周坚持学习编程算法并完成练习")) >= 70.0)
check("简答空回答0", _to_score(score_question(qobj("text", {"type": "text"}, None), "")) == 0.0)

# ------------------------------------------------------------------- #
# 4. 提交答卷（高分编程/逻辑/数据方向）
# ------------------------------------------------------------------- #
print("== 4. POST /assessment/submit ==")
answers = [
    {"question_id": qs[0]["id"], "answer": "C"},   # logic 100
    {"question_id": qs[1]["id"], "answer": 5},     # programming 量表 100
    {"question_id": qs[2]["id"], "answer": 5},     # data 100
    {"question_id": qs[3]["id"], "answer": 3},     # spatial 50
    {"question_id": qs[4]["id"], "answer": "A"},   # language 60
    {"question_id": qs[5]["id"], "answer": 4},     # hands_on 75
    {"question_id": qs[6]["id"], "answer": ["A", "B", "C"]},  # interest 60
    {"question_id": qs[7]["id"], "answer": "A"},   # interest 90 -> 均值75
    {"question_id": qs[8]["id"], "answer": ["B", "D"]},      # work_values 40
    {"question_id": qs[9]["id"], "answer": "希望成为 AI 算法工程师，因为喜欢用数据解决复杂智能问题"},
    {"question_id": qs[10]["id"], "answer": "希望掌握编程与算法并进入AI方向"},
    {"question_id": qs[11]["id"], "answer": "A"},  # programming 100 -> 均值100
]
r = client.post("/api/v1/assessment/submit", headers=h, json={"paper_id": paper_id, "answers": answers, "duration": 360})
check("submit 200", r.status_code == 200, str(r.status_code) + str(r.text))
sub = r.json()["data"]
check("返回 result_id", sub["result_id"] > 0, str(sub))
check("总分=75.0", sub["total_score"] == 75.0, str(sub["total_score"]))
check("Top1=AI/算法工程师", sub["top_job"] == "AI/算法工程师", str(sub["top_job"]))
result_id = sub["result_id"]

# 未作答全部题目的提交被拦截
r = client.post("/api/v1/assessment/submit", headers=h, json={"paper_id": paper_id, "answers": answers[:3]})
check("缺题提交 400", r.status_code == 400, str(r.status_code))

# ------------------------------------------------------------------- #
# 5. 结果详情
# ------------------------------------------------------------------- #
print("== 5. GET /assessment/result/{id} ==")
r = client.get(f"/api/v1/assessment/result/{result_id}", headers=h)
check("result 200", r.status_code == 200)
res = r.json()["data"]
check("维度得分10维", len(res["dimension_scores"]) == 10, str(set(res["dimension_scores"].keys())))
check("维度名中文", res["dimension_labels"]["logic"] == "逻辑")
check("六维能力分正确", (
    res["dimension_scores"]["logic"] == 100.0
    and res["dimension_scores"]["programming"] == 100.0
    and res["dimension_scores"]["data"] == 100.0
    and res["dimension_scores"]["spatial"] == 50.0
    and res["dimension_scores"]["hands_on"] == 75.0
), str(res["dimension_scores"]))
radar = res["radar_data"]["dimensions"]
check("雷达图6个点", len(radar) == 6 and all("name" in p and "score" in p for p in radar))
jobs = res["recommended_jobs"]
check("推荐3个岗位", len(jobs) == 3, str([j["job_name"] for j in jobs]))
check("岗位排序降序", jobs[0]["match_score"] >= jobs[1]["match_score"] >= jobs[2]["match_score"])
check("Top1匹配度>90", jobs[0]["match_score"] > 90, str(jobs[0]["match_score"]))
check("含推荐理由", bool(jobs[0]["reason"]))
check("含技能差距", len(jobs[0]["skill_gaps"]) > 0 and all("gap" in g for g in jobs[0]["skill_gaps"]))
check("推荐来源=rule", res["recommendation_source"] == "rule")
r = client.get(f"/api/v1/assessment/result/{result_id}")
check("他人无token 401", r.status_code == 401)
with ds.SessionLocal() as s:
    from app.models import AssessmentReport, LearningRecord
    from sqlalchemy import select, func
    n_reports = s.scalar(select(func.count(AssessmentReport.id)).where(AssessmentReport.user_id == uid))
    n_records = s.scalar(select(func.count(LearningRecord.id)).where(LearningRecord.user_id == uid))
check("同步写入测评报告", n_reports == 1, f"reports={n_reports}")
check("同步写入学习轨迹", n_records == 1, f"records={n_records}")

# ------------------------------------------------------------------- #
# 6. 画像
# ------------------------------------------------------------------- #
print("== 6. /persona/current 与 /persona/generate ==")
r = client.get("/api/v1/persona/current", headers=h)
check("current 200", r.status_code == 200)
check("测评后画像已自动生成(闭环2)", r.json()["data"] is not None, r.text)

r = client.post("/api/v1/persona/generate", headers=h)
check("generate 200", r.status_code == 200, str(r.status_code) + str(r.text))
gen = r.json()["data"]
p = gen["persona"]
check("画像 source_result_id 正确", gen["source_result_id"] == result_id)
check("画像含规则标签", len(p["persona_tags"]) > 0, str(p["persona_tags"]))
check("擅场标签含编程/数据/逻辑", any(k in p["persona_tags"] for k in ["编程潜力股", "数据敏感型", "逻辑缜密型"]), str(p["persona_tags"]))
check("AI未配置走规则综述", p["ai_enriched"] is False and bool(p["persona_summary"]))
check("目标职业=AI/算法工程师", p["target_job"] == "AI/算法工程师", str(p["target_job"]))
check("学习目标来自简答", "编程与算法" in (p["learning_goal"] or ""), str(p["learning_goal"]))
check("能力雷达6维", len(p["ability_radar"]["dimensions"]) == 6)
check("兴趣数据非空", bool(p["interest"]))
check("价值观数据非空", bool(p["values"]))

# 幂等：再次 generate 产生更新而非新建
with ds.SessionLocal() as s:
    from sqlalchemy import select
    from app.models import UserPersona
    cnt = len(list(s.scalars(select(UserPersona).where(UserPersona.user_id == uid))))
check("画像表仅1行(upsert)", cnt == 1, f"rows={cnt}")
r = client.get("/api/v1/persona/current", headers=h)
check("current 已有画像", r.json()["data"] is not None and r.json()["data"]["target_job"] == "AI/算法工程师")

# ------------------------------------------------------------------- #
# 7. 报告历史联动（模块2接口可见 career 报告）
# ------------------------------------------------------------------- #
print("== 7. 模块2报告历史联动 ==")
r = client.get("/api/v1/users/assessment-reports", headers=h, params={"page_size": 10})
reps = r.json()["data"]
check("报告列表含 career 报告", reps["total"] >= 1 and reps["items"][0]["report_type"] == "career", str(reps))

print(f"\n结果: PASS={PASS} FAIL={FAIL}")
raise SystemExit(1 if FAIL else 0)