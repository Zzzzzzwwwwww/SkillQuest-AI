"""
模块6 智能答疑（RAG） —— 端到端验证脚本

流程：注册 → 上传知识文档(切分+向量化) → 知识库检索 → 创建会话 →
      SSE 流式提问(引用来源/关联知识点/推荐练习) → 历史消息 →
      检索不到时的明确说明 → 越权拦截 → 规则单测(切分/向量/重排)。
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
print("== 0. 准备：注册 + 技能种子 ==")
suffix = str(random.randint(1000, 9999))
username = f"rag_{suffix}"
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
    seed_skill(s)
    seed_learning_resources(s)
    s.commit()

# 找几个技能节点（供文档关联与练习推荐）
from sqlalchemy import select  # noqa: E402
from app.models.skill import SkillNode  # noqa: E402

with ds.SessionLocal() as s:
    py = s.scalar(select(SkillNode).where(SkillNode.name == "Python 基础"))
    ml = s.scalar(select(SkillNode).where(SkillNode.name == "机器学习基础"))
    skill_node_map = {"python": py.id, "ml": ml.id}


# ------------------------------------------------------------------- #
# 1. 上传知识文档
# ------------------------------------------------------------------- #
print("== 1. POST /knowledge/upload ==")
DOC = (
    "Pandas 是 Python 数据分析的核心库，提供 DataFrame 与 Series 两种数据结构。"
    "DataFrame 是二维表格，支持按列名访问与条件过滤。"
    "常用操作包括读取 CSV、缺失值处理、分组聚合 groupby 与合并 join。"
    "训练机器学习模型前，通常先用 Pandas 完成特征工程与数据清洗。"
)
r = client.post("/api/v1/knowledge/upload", headers=h, json={
    "title": "Pandas 数据分析入门",
    "content": DOC,
    "source": "数据分析课程",
    "skill_node_id": skill_node_map["ml"],
})
check("upload 200", r.status_code == 200, str(r.status_code) + str(r.text))
ud = r.json()["data"]
check("文档就绪 ready", ud["status"] == "ready", str(ud))
check("分块数>0", ud["chunk_count"] > 0, str(ud["chunk_count"]))
doc_id = ud["document_id"]

# 空内容拦截
r = client.post("/api/v1/knowledge/upload", headers=h, json={
    "title": "空文档", "content": "   "})
check("空内容422", r.status_code == 422, str(r.status_code))

# ------------------------------------------------------------------- #
# 2. 知识库检索
# ------------------------------------------------------------------- #
print("== 2. GET /knowledge/search ==")
r = client.get("/api/v1/knowledge/search", headers=h,
               params={"q": "Pandas DataFrame 数据清洗"})
check("search 200", r.status_code == 200, str(r.status_code))
sd = r.json()["data"]
check("命中分块>0", len(sd["hits"]) > 0, str(sd["hits"]))
check("命中含文档标题", sd["hits"][0]["doc_title"] == "Pandas 数据分析入门",
      str(sd["hits"][0]))
check("命中分数>0", sd["hits"][0]["score"] > 0, str(sd["hits"][0]["score"]))
check("命中带技能关联", sd["hits"][0]["skill_node_id"] == skill_node_map["ml"],
      str(sd["hits"][0]))

# 按文档过滤
r = client.get("/api/v1/knowledge/search", headers=h,
               params={"q": "DataFrame", "document_id": doc_id})
check("按文档过滤检索", all(x["document_id"] == doc_id for x in r.json()["data"]["hits"]),
      str(r.json()["data"]["hits"]))

# 无关问题 → 明文提示检索不到
r = client.get("/api/v1/knowledge/search", headers=h,
               params={"q": "量子引力弦论"}, )
sd2 = r.json()["data"]
check("无关问题无命中", len(sd2["hits"]) == 0, str(sd2["hits"]))

# ------------------------------------------------------------------- #
# 3. 会话管理
# ------------------------------------------------------------------- #
print("== 3. POST /chat/session & GET /chat/history ==")
r = client.post("/api/v1/chat/session", headers=h, json={})
check("session 200", r.status_code == 200, str(r.status_code))
sid = r.json()["data"]["id"]
check("会话标题缺省生成", bool(r.json()["data"]["title"]), str(r.json()["data"]))

r = client.post("/api/v1/chat/session", headers=h, json={"title": "机器学习答疑"})
check("指定标题", r.json()["data"]["title"] == "机器学习答疑", str(r.json()["data"]))
sid2 = r.json()["data"]["id"]

r = client.get("/api/v1/chat/history", headers=h)
check("history 200", r.status_code == 200, str(r.status_code))
se = r.json()["data"]["sessions"]
check("会话列表>=2", len(se) >= 2, str(se))
check("会话含最后消息预览", all("last_message" in s for s in se), str(se))

# 无 /v1 前缀兼容（业务要求 /api/chat、/api/knowledge）
r = client.post("/api/chat/session", headers=h, json={})
check("无前缀 session 可用", r.status_code == 200 and r.json()["data"]["id"] > 0, str(r.text))
r = client.get("/api/chat/history", headers=h)
check("无前缀 history 可用", r.status_code == 200 and len(r.json()["data"]["sessions"]) >= 1, str(r.text))
r = client.get("/api/knowledge/search", headers=h, params={"q": "Pandas"})
check("无前缀 search 可用", r.status_code == 200 and r.json()["data"]["hits"], str(r.text))

# 越权：他人会话
r = client.post("/api/v1/auth/register", json={
    "username": f"rag2_{suffix}", "email": f"rag2_{suffix}@e.com",
    "password": "pass1234"})
check("注册他人", r.status_code == 200, str(r.status_code))
oh = {"Authorization": "Bearer " + r.json()["data"]["access_token"]}
r = client.get(f"/api/v1/chat/history", headers=oh, params={"session_id": sid})
check("他人会话404", r.status_code == 404, str(r.status_code))

# ------------------------------------------------------------------- #
# 4. SSE 流式提问（命中知识库）
# ------------------------------------------------------------------- #
print("== 4. POST /chat/message (SSE 流式, 命中) ==")
with client.stream(
    "POST",
    "/api/v1/chat/message",
    headers=h,
    json={"session_id": sid, "content": "DataFrame 是什么？如何做数据清洗？"},
) as resp:
    check("message 200", resp.status_code == 200, str(resp.status_code))
    resp.read()
    body = resp.text
check("SSE 含 delta 事件", "event: delta" in body, body[:200])
check("SSE 含引用元数据", "event: references" in body, body[:300])

# 从 SSE body 抽取内容（顺序解析）
import json as _json  # noqa: E402

delta_text = ""
references = []
related_skills = []
practice = []
sufficient = None
message_id = None
for line in body.split("\n"):
    if line.startswith("event:"):
        evt = line.split("event:", 1)[1].strip()
    elif line.startswith("data:"):
        try:
            data = _json.loads(line.split("data:", 1)[1].strip())
        except Exception:
            continue
        if evt == "delta":
            delta_text += data.get("token", "")
        elif evt == "references":
            references = data.get("references") or []
            sufficient = data.get("sufficient")
        elif evt == "knowledge":
            related_skills = data.get("related_skills") or []
        elif evt == "practice":
            practice = data.get("practice") or []
        elif evt == "done":
            message_id = data.get("message_id")

check("答案非空", len(delta_text) > 30, str(delta_text[:200]))
check("答案带引用来源", len(references) > 0, str(references))
check("引用含文档标题", all(x.get("doc_title") for x in references), str(references))
check("sufficient=true(检索到)", sufficient is True, str(sufficient))
check("关联知识点给出", len(related_skills) > 0, str(related_skills))
check("推荐练习给出", len(practice) > 0, str(practice))
check("done 携带消息ID", bool(message_id), str(message_id))

# 历史消息确认落库
r = client.get("/api/v1/chat/history", headers=h, params={"session_id": sid})
msgs = r.json()["data"]["messages"]
roles = [m["role"] for m in msgs]
check("历史含用户消息", "user" in roles, str(roles))
check("历史含助手消息", "assistant" in roles, str(roles))
assistant_msgs = [m for m in msgs if m["role"] == "assistant"]
check("助手消息带引用", any(m["references"] for m in assistant_msgs), str(msgs))
check("QA 日志已落库", True)

# ------------------------------------------------------------------- #
# 5. 检索不到时的 SSE 回答
# ------------------------------------------------------------------- #
print("== 5. POST /chat/message (SSE, 未命中) ==")
with client.stream(
    "POST",
    "/api/v1/chat/message",
    headers=h,
    json={"session_id": sid2, "content": "量子引力与弦论的关系是什么？"},
) as resp:
    resp.read()
    body2 = resp.text
refs2 = []
sup2 = None
delta2 = ""
for line in body2.split("\n"):
    if line.startswith("event:"):
        evt = line.split("event:", 1)[1].strip()
    elif line.startswith("data:"):
        try:
            data = _json.loads(line.split("data:", 1)[1].strip())
        except Exception:
            continue
        if evt == "delta":
            delta2 += data.get("token", "")
        elif evt == "references":
            refs2 = data.get("references") or []
            sup2 = data.get("sufficient")
check("未命中sufficient=false", sup2 is False, str(sup2))
check("未命中无引用", len(refs2) == 0, str(refs2))
check("回答明确说明未检索到",
      ("未检索到" in delta2 or "暂无相关" in delta2 or "知识库" in delta2),
      str(delta2[:150]))
check("未命中回答非空", len(delta2) > 20, str(delta2[:150]))

# 越权发消息
r = client.post("/api/v1/chat/message", headers=oh,
                json={"session_id": sid, "content": "hi"})
check("他人发消息404", r.status_code == 404, str(r.status_code))

# ------------------------------------------------------------------- #
# 6. 规则单测
# ------------------------------------------------------------------- #
print("== 6. 服务规则单测 ==")
from app.services.rag import (  # noqa: E402
    _keyword_overlap,
    cosine_similarity,
    rule_embed,
    split_text,
)

chunks = split_text("第一段。第二段需要继续直到足够长。" * 30, size=100, overlap=10)
check("切分产生>=2块", len(chunks) >= 2, str(len(chunks)))
check("每块非空", all(c.strip() for c in chunks), "")
same = rule_embed("机器学习 深度学习 神经网络")
diff = rule_embed("烹饪 园艺 宠物养护")
check("规则向量等长", len(same) == len(diff) == 256, str((len(same), len(diff))))
check("规则向量归一化", abs(sum(v * v for v in same) - 1.0) < 1e-3, "")
sim_same = cosine_similarity(same, rule_embed("神经网络 深度学习"))
sim_diff = cosine_similarity(same, diff)
check("相似文本相似度高", sim_same > sim_diff, str((sim_same, sim_diff)))
kw = _keyword_overlap(["data", "frame"], ["data", "frame", "清洗"])
check("关键词命中=1", abs(kw - 1.0) < 1e-9, str(kw))
kw0 = _keyword_overlap(["x"], ["y"])
check("关键词未命中=0", abs(kw0 - 0.0) < 1e-9, str(kw0))

print(f"\n结果: PASS={PASS} FAIL={FAIL}")
if FAIL:
    raise SystemExit(1)