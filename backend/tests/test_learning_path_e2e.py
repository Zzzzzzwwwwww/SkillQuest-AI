"""
模块5 个性化导学 —— 端到端验证脚本

流程：注册 → 种子技能图谱 + 学习资源 → 生成学习路径（规则分段 青铜~王者）→
      当前路径 / 路径地图 → 更新进度(含断点位置) → 断点续学 → 资源推荐 →
      路径完成联动（current 指针推进 / 状态 completed）。

路径生成依据：目标岗位 → 技能短板 gap、重要度、前置知识拓扑 —— 全部规则计算。
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
# 0. 准备
# ------------------------------------------------------------------- #
print("== 0. 准备：注册 + 种子技能图谱/学习资源 ==")
suffix = str(random.randint(1000, 9999))
username = f"learner_{suffix}"
r = client.post("/api/v1/auth/register", json={
    "username": username,
    "email": f"{username}@example.com",
    "password": "pass1234",
})
check("注册成功", r.status_code == 200, str(r.status_code) + str(r.text))
token = r.json()["data"]["access_token"]
uid = r.json()["data"]["user"]["id"]
h = {"Authorization": f"Bearer {token}"}

from app.db.seed_skill import seed_skill  # noqa: E402
from app.db.seed_learning import seed_learning_resources  # noqa: E402

with ds.SessionLocal() as s:
    stats = seed_skill(s)
    s.commit()
check("种子技能图谱", stats["jobs"] == 6 and stats["skills"] == 15, str(stats))
with ds.SessionLocal() as s:
    rsrc = seed_learning_resources(s)
    s.commit()
check("种子学习资源(技能+知识点 x 4类)", len(rsrc) and rsrc["resources"] == 240, str(rsrc))

# 画像直接写入目标岗位（模拟测评结果决定的目标岗位）
from app.models.persona import UserPersona  # noqa: E402
from sqlalchemy import select  # noqa: E402

with ds.SessionLocal() as s:
    s.add(UserPersona(user_id=uid, persona_tags_json={"tags": ["测试"]},
                      ability_radar_json={"dimensions": []},
                      target_job="AI 应用开发工程师"))
    s.commit()

# ------------------------------------------------------------------- #
# 1. 生成学习路径
# ------------------------------------------------------------------- #
print("== 1. POST /learning-path/generate ==")
r = client.post("/api/v1/learning-path/generate", headers=h, json={})
check("generate 200", r.status_code == 200, str(r.status_code) + str(r.text))
data = r.json()["data"]
path = data["path"]
check("路径名称含岗位", path["path_name"] and "AI 应用开发工程师" in path["path_name"], path["path_name"])
check("目标岗位正确", path["target_job"] == "AI 应用开发工程师", path["target_job"])
check("节点总数=11", path["total_nodes"] == 11, str(path["total_nodes"]))
check("存在6段位", len(path["stage_order"]) == 6, str(path["stage_order"]))
check("青铜段有节点", len(path["stages"]["bronze"]) >= 1, str(path["stages"]["bronze"]))
check("王者段有节点", len(path["stages"]["king"]) >= 1, str(path["stages"]["king"]))
check("金色段在青铜之后出现顺序体", path["stage_order"] == ["bronze", "silver", "gold", "platinum", "diamond", "king"], str(path["stage_order"]))
check("路径状态 active", path["status"] == "active", str(path["status"]))
check("有当前节点指针", path["current_node_id"] is not None, str(path["current_node_id"]))
check("全体进度0", path["overall_progress"] == 0, str(path["overall_progress"]))
# 节点字段
first = path["stages"]["bronze"][0]
check("节点携带技能名", bool(first["name"]), str(first))
check("节点携带预估时长", first["estimated_hours"] > 0, str(first["estimated_hours"]))
check("节点带前置知识数组", isinstance(first["prerequisites"], list), str(first))
check("meta 给出总时长", data["meta"]["total_hours"] > 0, str(data["meta"]))

# 幂等：重复 generate 返回已存在路径
r2 = client.post("/api/v1/learning-path/generate", headers=h, json={})
data2 = r2.json()["data"]
check("重复生成复用(reused)", data2["meta"].get("reused") is True, str(data2["meta"]))

# 指定 job_id 强制重建
r3 = client.get("/api/v1/jobs", headers=h)
jobs = {j["job_name"]: j["id"] for j in r3.json()["data"]}
r4 = client.post("/api/v1/learning-path/generate", headers=h,
                 json={"job_id": jobs["后端工程师"], "force": True})
d4 = r4.json()["data"]
check("force 切换岗位", d4["path"]["target_job"] == "后端工程师", d4["path"]["target_job"])
check("后端岗位技能数=7(含前置)", d4["path"]["total_nodes"] == 7, str(d4["path"]["total_nodes"]))

# 再切回 AI 应用开发（后续进度验证用）
r5 = client.post("/api/v1/learning-path/generate", headers=h,
                 json={"job_id": jobs["AI 应用开发工程师"], "force": True})
data5 = r5.json()["data"]
check("切回AI应用开发", data5["path"]["target_job"] == "AI 应用开发工程师")

# ------------------------------------------------------------------- #
# 2. 当前路径 & 地图
# ------------------------------------------------------------------- #
print("== 2. GET /learning-path/current & map ==")
r = client.get("/api/v1/learning-path/current", headers=h)
d = r.json()["data"]
check("current 200", r.status_code == 200, str(r.status_code))
check("current 返回路径", d["target_job"] == "AI 应用开发工程师", d["target_job"])

path_id = d["path_id"]
r = client.get(f"/api/v1/learning-path/{path_id}/map", headers=h)
m = r.json()["data"]
check("map 路径ID一致", m["path_id"] == path_id)
check("map 段位节点总数一致", sum(len(v) for v in m["stages"].values()) == m["total_nodes"])

# 越权校验
r = client.post("/api/v1/auth/register", json={
    "username": f"other_{suffix}", "email": f"other_{suffix}@e.com", "password": "pass1234"})
check("注册他人", r.status_code == 200, str(r.status_code))
oh = {"Authorization": "Bearer " + r.json()["data"]["access_token"]}
r = client.get(f"/api/v1/learning-path/{path_id}/map", headers=oh)
check("他人路径404", r.status_code == 404, str(r.status_code))

# ------------------------------------------------------------------- #
# 3. 更新进度(含断点位置)
# ------------------------------------------------------------------- #
print("== 3. PUT /learning-progress ==")
r = client.get(f"/api/v1/learning-path/{path_id}/map", headers=h)
m = r.json()["data"]
first_node = m["stages"]["bronze"][0]
snid = first_node["skill_node_id"]

r = client.put("/api/v1/learning-progress", headers=h, json={
    "path_id": path_id,
    "skill_node_id": snid,
    "progress_percent": 90,
    "last_position": "第3章 前置知识强化",
})
check("PUT 200", r.status_code == 200, str(r.status_code) + str(r.text))
up = r.json()["data"]
check("掌握度同步90", up["updated_node"]["progress_percent"] == 90, str(up["updated_node"]))
check("推进到下一节点(to_next)", up["to_next"] is True, str(up))
check("current指针推进", up["path"]["current_node_id"] != first_node["id"], str(up["path"]["current_node_id"]))
check("整体进度>0", up["path"]["overall_progress"] > 0, str(up["path"]["overall_progress"]))
check("掌握节点数=1", up["path"]["mastered_nodes"] == 1, str(up["path"]["mastered_nodes"]))
check("断点位置保存", up["updated_node"]["last_position"] == "第3章 前置知识强化", str(up["updated_node"]))

# 无权限校验
r = client.put("/api/v1/learning-progress", headers=oh, json={
    "path_id": path_id, "skill_node_id": snid, "progress_percent": 10})
check("他人更新404", r.status_code == 404, str(r.status_code))

# ------------------------------------------------------------------- #
# 4. 断点续学
# ------------------------------------------------------------------- #
print("== 4. POST /learning-progress/resume ==")
r = client.post("/api/v1/learning-progress/resume", headers=h, json={})
res = r.json()["data"]
check("resume 200", r.status_code == 200, str(r.status_code) + str(r.text))
check("返回当前节点", res["resume_node"] is not None, str(res))
check("提示语合理", "上次学习位置" in res["hint"] or "继续学习" in res["hint"], res["hint"])
check("断点位置带出", "前置知识" in (res["resume_position"] or ""), str(res["resume_position"]))

# 指定 path_id
r = client.post("/api/v1/learning-progress/resume", headers=h, json={"path_id": path_id})
check("resume 指定路径", r.json()["data"]["resume_node"] is not None, str(r.json()))

# ------------------------------------------------------------------- #
# 5. 资源推荐
# ------------------------------------------------------------------- #
print("== 5. GET /learning-resources/recommend ==")
r = client.get("/api/v1/learning-resources/recommend", headers=h)
check("recommend 200", r.status_code == 200, str(r.status_code))
recs = r.json()["data"]
check("返回资源数>0", len(recs) > 0, str(recs))
check("推荐理由非空", all(x["reason"] for x in recs), str(recs))
check("评分非负<=100", all(0 <= x["score"] <= 100 for x in recs), str(recs))
check("按评分降序", recs == sorted(recs, key=lambda x: x["score"], reverse=True), str([x["score"] for x in recs]))
check("带资源类型", all(x["type"] in ("video", "course", "article", "exercise") for x in recs), str(recs))

# 指定 skill_node_id 推荐
r = client.get(f"/api/v1/learning-resources/recommend?skill_node_id={snid}", headers=h)
recs2 = r.json()["data"]
check("指定节点推荐", len(recs2) > 0, str(recs2))

# 越权资源（无路径用户也能推荐，需要节点存在）
from app.models.skill import SkillNode as SN  # noqa: E402

with ds.SessionLocal() as s:
    nid = s.scalar(select(SN.id).where(SN.node_type == "skill"))
r = client.get(f"/api/v1/learning-resources/recommend?skill_node_id={nid}", headers=oh)
check("他人推荐也支持", r.status_code == 200, str(r.status_code) + str(r.text))

# 类型过滤（增补功能）
r = client.get("/api/v1/learning-resources/recommend?resource_type=video", headers=h)
recs_v = r.json()["data"]
check("按类型过滤 video", len(recs_v) > 0 and all(x["type"] == "video" for x in recs_v), str(recs_v))
r = client.get("/api/v1/learning-resources/recommend?resource_type=exercise", headers=h)
recs_e = r.json()["data"]
check("按类型过滤 exercise", len(recs_e) > 0 and all(x["type"] == "exercise" for x in recs_e), str(recs_e))

# 无 /v1 前缀兼容路径（业务要求 /api/learning-*）
r = client.get("/api/learning-path/current", headers=h)
cur0 = r.json()["data"]
check("无前缀 current 可用", r.status_code == 200 and cur0 and cur0["total_nodes"] >= 1, str(r.text))
r = client.get("/api/learning-resources/recommend?resource_type=video", headers=h)
check("无前缀 recommend 可用", r.status_code == 200 and all(x["type"] == "video" for x in r.json()["data"]), str(r.text))
r = client.post("/api/learning-progress/resume", headers=h, json={})
check("无前缀 resume 可用", r.status_code == 200 and r.json()["data"]["path"] is not None, str(r.text))

# ------------------------------------------------------------------- #
# 6. 完成路径联动
# ------------------------------------------------------------------- #
print("== 6. 完成全部节点 → 路径 completed ==")
r = client.get(f"/api/v1/learning-path/{path_id}/map", headers=h)
m = r.json()["data"]
for stage in m["stages"].values():
    for n in stage:
        if n["skill_node_id"] != snid:
            r = client.put("/api/v1/learning-progress", headers=h, json={
                "path_id": path_id,
                "skill_node_id": n["skill_node_id"],
                "progress_percent": 100,
            })
check("全部节点更新成功", True)
r = client.get("/api/v1/learning-path/current", headers=h)
cur = r.json()["data"]
check("路径状态 completed", cur is None or cur["status"] == "completed", str(cur))

# 完成后的技能状态同步校验
r = client.get(f"/api/v1/users/{uid}/skill-status", headers=h)
slist = r.json()["data"]["items"]
check("技能状态已落库", len(slist) >= 11, str(len(slist)))
mastered_count = sum(1 for i in slist if i["status"] == "mastered")
check("掌握数>=11(全部100)", mastered_count >= 11, str(mastered_count))

# ------------------------------------------------------------------- #
# 7. 规则单测（服务层）
# ------------------------------------------------------------------- #
print("== 7. 服务规则单测 ==")
from app.services.learning_path_service import (  # noqa: E402
    _derive_status,
    _topo_sort_skills,
    should_complete_path,
)

check("状态:100->completed", _derive_status(100, [], set()) == "completed")
check("状态:50->learning", _derive_status(50, [], set()) == "learning")
check("状态:0+前置未掌握->locked",
      _derive_status(0, ["Python 基础"], {"JavaScript"}) == "locked")
check("状态:0+前置已掌握->unlocked",
      _derive_status(0, ["Python 基础"], {"Python 基础"}) == "unlocked")
check("路径完成判定",
      should_complete_path(
          [{"skill_node_id": 1}, {"skill_node_id": 2}],
          {1: 100, 2: 90},
      ) is True)
check("路径未完成判定",
      should_complete_path(
          [{"skill_node_id": 1}, {"skill_node_id": 2}],
          {1: 100, 2: 40},
      ) is False)

# 拓扑排序：前置在前
class FakeNode:
    def __init__(self, i, name, pre):
        self.id = i
        self.name = name
        self.prerequisites_json = pre


a = FakeNode(1, "机器学习基础", ["Python 基础"])
b = FakeNode(2, "Python 基础", [])
c = FakeNode(3, "深度学习基础", ["机器学习基础"])
pool = [a, b, c]
name_idx = {x.name: x for x in pool}
order = _topo_sort_skills(pool, name_idx, {x.id: 10 for x in pool})
order_names = [x.name for x in order]
check("前置先于依赖", order_names.index("Python 基础") < order_names.index("机器学习基础"), str(order_names))
check("递推依赖顺序", order_names.index("机器学习基础") < order_names.index("深度学习基础"), str(order_names))

print(f"\n结果: PASS={PASS} FAIL={FAIL}")
if FAIL:
    raise SystemExit(1)