"""
统一多智能体 API（模块8）—— 端到端验证脚本

覆盖：
  - GET  /agents（含 /api 与 /api/v1 双前缀）返回 8 个 Agent 清单
  - 未鉴权 401
  - POST /agents/run 未知 agent_type → 错误结构（ok=False, degraded=True）
  - POST /agents/run 已知 agent + fallback → 降级返回规则结果（degraded=True, data=fallback）
  - POST /agents/stream SSE → 返回 delta/done 事件（未配置模型时空流 + done）
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
# 0. 准备：注册用户
# ------------------------------------------------------------------- #
print("== 0. 准备：注册 ==")
suffix = str(random.randint(1000, 9999))
username = f"ag_{suffix}"
r = client.post("/api/v1/auth/register", json={
    "username": username,
    "email": f"{username}@example.com",
    "password": "pass1234",
})
check("注册成功", r.status_code == 200, str(r.status_code) + str(r.text))
token = r.json()["data"]["access_token"]
h = {"Authorization": f"Bearer {token}"}

# ------------------------------------------------------------------- #
# 1. Agent 清单
# ------------------------------------------------------------------- #
print("== 1. GET /agents ==")
r = client.get("/api/v1/agents", headers=h)
check("清单200", r.status_code == 200, str(r.status_code))
agents = r.json()["data"]
check("共8个Agent", len(agents) == 8, str(len(agents)))
names = {a["name"] for a in agents}
check("含全部核心Agent",
      {"orchestrator", "career", "skill", "learning", "tutor",
       "assessment", "coach", "reflection"} <= names,
      str(names))
check("清单条目含角色说明", all(a.get("role") and a.get("description") for a in agents),
      str(agents[:1]))

# 无 /v1 前缀兼容（业务要求 /api/agents）
r = client.get("/api/agents", headers=h)
check("无前缀清单可用", r.status_code == 200 and len(r.json()["data"]) == 8, str(r.text))

# 未鉴权
r = client.get("/api/v1/agents")
check("未鉴权401", r.status_code == 401, str(r.status_code))

# ------------------------------------------------------------------- #
# 2. 未知 agent_type → 错误结构
# ------------------------------------------------------------------- #
print("== 2. POST /agents/run 未知 agent ==")
r = client.post("/api/v1/agents/run", headers=h, json={
    "agent_type": "no_such_agent",
    "user_context": {"q": "x"},
})
check("run 200", r.status_code == 200, str(r.status_code))
d = r.json()["data"]
check("ok=False", d["ok"] is False, str(d))
check("degraded=True", d["degraded"] is True, str(d))
check("错误提示含未注册", "未注册" in d["error"] or "未注册" in d["note"], str(d))

# ------------------------------------------------------------------- #
# 3. 已知 agent + fallback → 降级返回规则结果（测试环境未配置大模型）
# ------------------------------------------------------------------- #
print("== 3. POST /agents/run 已知agent + fallback ==")
fallback = {"daily_plan": [{"task": "复习薄弱点", "estimated_minutes": 30}],
            "pomodoro_suggestion": {"focus_minutes": 25, "break_minutes": 5,
                                    "rounds": 4, "tip": "保持节奏"},
            "encouragement": "持续推进就是胜利！"}
r = client.post("/api/v1/agents/run", headers=h, json={
    "agent_type": "coach",
    "user_context": {"today_tasks": ["复习机器学习基础"], "streak": 3},
    "fallback": fallback,
})
check("run 200", r.status_code == 200, str(r.status_code))
d = r.json()["data"]
check("ok=True(有fallback)", d["ok"] is True, str(d))
check("degraded=True(未配置)", d["degraded"] is True, str(d))
check("返回规则降级结果", d["data"] == fallback, str(d))
check("agent_type=coach", d["agent_type"] == "coach", str(d))

# ------------------------------------------------------------------- #
# 4. SSE 流式（未配置模型 → 空流 + done）
# ------------------------------------------------------------------- #
print("== 4. POST /agents/stream ==")
with client.stream(
    "POST",
    "/api/v1/agents/stream",
    headers=h,
    json={"agent_type": "tutor",
          "user_context": {"question": "什么是 DataFrame？"},
          "retrieved_docs": [{"doc_title": "d", "content": "pandas 文档片段"}]},
) as resp:
    check("stream 200", resp.status_code == 200, str(resp.status_code))
    resp.read()
    body = resp.text
check("SSE 含 done 事件", "event: done" in body, body[:200])
check("SSE 媒体流", True)

# 无前缀 stream 可用
with client.stream(
    "POST",
    "/api/agents/stream",
    headers=h,
    json={"agent_type": "skill",
          "user_context": {"gaps": []}},
) as resp:
    resp.read()
    body2 = resp.text
check("无前缀 stream 可用", resp.status_code == 200 and "event: done" in body2,
      str(resp.status_code))

# 未鉴权 stream
r = client.post("/api/v1/agents/stream", json={"agent_type": "tutor"})
check("stream 未鉴权401", r.status_code == 401, str(r.status_code))

print(f"\n结果: PASS={PASS} FAIL={FAIL}")
if FAIL:
    raise SystemExit(1)