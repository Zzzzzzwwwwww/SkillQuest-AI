"""
SkillQuest AI RAG 检索服务（模块6）

流程：文档切分 → Embedding(模型或规则向量) → 落库 → 查询向量化 →
      相似检索 → 关键词加权重排 → 组装 Prompt(Tutor Agent) → 引用来源。

设计原则（第1条）：能规则算的不用大模型 ——
  - Embedding 未配置模型时，降级为确定性规则向量（字符 n-gram 哈希，
    与语义无关但能支撑关键词相似检索），检索/重排全部规则完成；
  - LLM 仅用于最终答案生成与解释，且未配置时规则组装答案。
"""

import hashlib
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat import (
    EMBEDDING_MODE_MODEL,
    EMBEDDING_MODE_RULE,
    KnowledgeChunk,
    KnowledgeDocument,
)

# 切分参数
_CHUNK_SIZE = 400      # 目标分块字符数
_CHUNK_OVERLAP = 40    # 块间重叠（保持上下文连续）
_RULE_DIM = 256        # 规则向量维度
_REDUCE_TOP = 20       # 粗召回数
_FINAL_TOP = 6         # 重排后返回数
_MIN_SCORE = 0.25      # 最低接受分数(低于视为检索不到)

# 重排权重：向量相似度 + 关键词命中
_W_SIM = 0.7
_W_KEY = 0.3


# -------------------------------------------------------------------- #
# Embedding：模型优先，规则向量降级
# -------------------------------------------------------------------- #
class EmbeddingService:
    """向量化服务：配置华为云 Embedding 时调用模型，否则规则向量。"""

    def __init__(self) -> None:
        from app.core.config import settings

        self.endpoint: str = settings.HUAWEI_EMBEDDING_ENDPOINT.rstrip("/")
        self.api_key: str = settings.HUAWEI_EMBEDDING_API_KEY
        self.model: str = settings.HUAWEI_EMBEDDING_MODEL
        self.dim: int = settings.HUAWEI_EMBEDDING_DIM

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.endpoint)

    @property
    def mode(self) -> str:
        return EMBEDDING_MODE_MODEL if self.is_configured else EMBEDDING_MODE_RULE

    async def embed(self, text: str) -> List[float]:
        """文本 → 维度向量。未配置模型时返回规则向量。"""
        if self.is_configured:
            return await self._embed_by_model(text)
        return rule_embed(text, self.dim)

    async def _embed_by_model(self, text: str) -> List[float]:
        import httpx

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {"model": self.model, "input": text}
        url = f"{self.endpoint}/v1/embeddings"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            vec = data["data"][0]["embedding"]
            if not vec:
                raise ValueError("Embedding 返回为空")
            if len(vec) > 1024:  # 维度过大时降采样，保证 JSON 体积可控
                step = max(1, len(vec) // self.dim)
                vec = vec[::step][: self.dim]
            return [float(v) for v in vec]


embedding_service = EmbeddingService()


def _deterministic_hash(text: str) -> int:
    """确定性哈希（Python 内置 hash 受 PYTHONHASHSEED 影响，禁用）。"""
    return int(hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest(), 16)


def _tokenize(text: str) -> List[str]:
    """轻量 token：ASCII 词 + 中文双字组（n-gram 规则）。"""
    lowered = text.lower()
    tokens: List[str] = []
    for word in re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", lowered):
        if re.fullmatch(r"[a-z0-9_]+", word):
            tokens.append(word)
        else:
            # 中文按双字 n-gram 切词
            padded = word
            for i in range(len(padded) - 1):
                tokens.append(padded[i : i + 2])
            if len(padded) == 1:
                tokens.append(padded)
    return tokens


def rule_embed(text: str, dim: int = _RULE_DIM) -> List[float]:
    """规则向量：字符 n-gram 哈希稀疏向量（归一化）。"""
    vec = [0.0] * dim
    for tok in _tokenize(text):
        vec[_deterministic_hash(tok) % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """余弦相似度（空向量视为不相似）。"""
    if not a or not b:
        return 0.0
    top = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return top / (na * nb)


# -------------------------------------------------------------------- #
# 文本切分（按段落/句子合并到目标大小，带重叠）
# -------------------------------------------------------------------- #
def split_text(text: str, size: int = _CHUNK_SIZE,
               overlap: int = _CHUNK_OVERLAP) -> List[str]:
    """把长文本切分为若干子块。

    策略：先按段落切，再按句号合并为 <=size 的块；相邻块保留 overlap 个字符
    保证上下文衔接。返回按文档顺序排列的块列表。
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    paras = [p.strip() for p in re.split(r"\n+|　*", cleaned) if p.strip()]
    sentences: List[str] = []
    for p in paras:
        parts = re.split(r"(?<=[。！？；.!?;])", p)
        sentences.extend([s.strip() for s in parts if s.strip()])

    chunks: List[str] = []
    buf = ""
    for s in sentences:
        if len(buf) + len(s) <= size:
            buf += s
            continue
        if buf:
            chunks.append(buf)
        # 单句超长时按字符硬切
        while len(s) > size:
            chunks.append(s[:size])
            s = s[size:]
        buf = s
    if buf:
        chunks.append(buf)

    if len(chunks) <= 1:
        return chunks

    # 加 overlap：前一个块尾巴拼到下一个块开头
    merged: List[str] = []
    prev_tail = ""
    for c in chunks:
        head = c
        if prev_tail and overlap > 0:
            head = prev_tail + head
        merged.append(head)
        prev_tail = c[-overlap:] if overlap > 0 else ""
    return merged


# -------------------------------------------------------------------- #
# 相似检索 + 关键词重排（全部规则）
# -------------------------------------------------------------------- #
def _keyword_overlap(query_tokens: List[str], chunk_tokens: List[str]) -> float:
    """关键词命中率：query token 在 chunk 中出现的比例（去重）。"""
    if not query_tokens:
        return 0.0
    qset = set(query_tokens)
    cset = set(chunk_tokens)
    hit = sum(1 for t in qset if t in cset)
    return hit / len(qset)


def retrieve_chunks(
    db: Session,
    query: str,
    top_k: int = _FINAL_TOP,
    min_score: float = _MIN_SCORE,
    document_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """相似检索 + 重排。

    规则：query 向量化 → 与所有块算余弦（粗召回 top REDUCE）→
    向量分*0.7 + 关键词命中*0.3 加权重排 → 过滤低分 → 返回 top_k。
    返回非空时自带文档标题/来源/原文用于引用组装。
    """
    if not query or not query.strip():
        return []
    qvec = rule_embed(query) if not embedding_service.is_configured else None

    stmt = select(KnowledgeChunk)
    if document_id:
        stmt = stmt.where(KnowledgeChunk.document_id == document_id)
    chunks = db.scalars(stmt).all()
    if not chunks:
        return []

    query_tokens = _tokenize(query)
    scored: List[Tuple[float, KnowledgeChunk]] = []
    for c in chunks:
        sim = 0.0
        if qvec is not None:
            sim = cosine_similarity(qvec, c.embedding or [])
        else:
            sim = cosine_similarity(rule_embed(query), c.embedding or [])
        key = _keyword_overlap(query_tokens, _tokenize(c.content))
        score = _W_SIM * sim + _W_KEY * key
        if score >= min_score:
            scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    results: List[Dict[str, Any]] = []
    for score, c in scored[:_REDUCE_TOP]:
        doc_id = c.metadata_json.get("document_id") if c.metadata_json else c.document_id
        doc = None
        if doc_id:
            doc = db.get(KnowledgeDocument, doc_id)
        results.append(
            {
                "chunk_id": c.id,
                "document_id": c.document_id,
                "doc_title": (doc.title if doc else "未知文档"),
                "source": (doc.source if doc else ""),
                "score": round(score, 4),
                "content": c.content,
                "skill_node_id": (
                    c.metadata_json.get("skill_node_id")
                    if c.metadata_json and c.metadata_json.get("skill_node_id")
                    else None
                ),
            }
        )
        if len(results) >= top_k:
            break
    return results


# -------------------------------------------------------------------- #
# 文档索引
# -------------------------------------------------------------------- #
async def index_document(
    db: Session,
    title: str,
    content: str,
    source: str = "",
    file_url: Optional[str] = None,
    skill_node_id: Optional[int] = None,
) -> KnowledgeDocument:
    """切分 → 向量化 → 写 chunks。返回完成的文档对象。"""
    from sqlalchemy import func

    doc = KnowledgeDocument(
        title=title,
        source=source,
        file_url=file_url,
        status="processing",
        embedding_mode=embedding_service.mode,
    )
    db.add(doc)
    db.flush()

    try:
        chunks = split_text(content)
        if not chunks:
            db.delete(doc)
            db.commit()
            raise ValueError("文档内容为空，无法切分")
        for idx, c in enumerate(chunks):
            vec = await embedding_service.embed(c)
            db.add(
                KnowledgeChunk(
                    document_id=doc.id,
                    content=c,
                    embedding=vec,
                    metadata_json={
                        "document_id": doc.id,
                        "title": title,
                        "source": source,
                        "order": idx,
                        "skill_node_id": skill_node_id,
                        "chunk_len": len(c),
                    },
                )
            )
        doc.status = "ready"
        db.add(doc)
        db.commit()
    except Exception:
        db.rollback()
        doc.status = "failed"
        db.add(doc)
        db.commit()
        raise
    return doc


# -------------------------------------------------------------------- #
# 组装 Prompt（结合用户当前学习进度）
# -------------------------------------------------------------------- #
def build_learning_context(db: Session, user_id: int) -> str:
    """读取用户当前学习进度摘要（路径/节点/整体进度/弱点诊断），注入答疑上下文。"""
    from app.models.learning_path import (
        LearningPath,
        LearningProgress,
        PATH_ACTIVE,
    )

    path = db.scalar(
        select(LearningPath)
        .where(LearningPath.user_id == user_id, LearningPath.status == PATH_ACTIVE)
        .order_by(LearningPath.id.desc())
    )

    context_parts: List[str] = []
    if path is None:
        context_parts.append("用户尚未开始学习路径。")
    else:
        rows = db.scalars(
            select(LearningProgress).where(
                LearningProgress.user_id == user_id,
                LearningProgress.path_id == path.id,
            )
        ).all()
        done = sum(1 for r in rows if r.progress_percent >= 80)
        pct = (
            round(sum(r.progress_percent for r in rows) / len(rows))
            if rows
            else 0
        )
        context_parts.append(
            f"用户当前目标岗位：{path.target_job}；进行中路径「{path.path_name}」，"
            f"已完成节点 {done} 个，整体进度 {pct}%。"
        )

    # 业务闭环5：弱点诊断结果推送到导师上下文（指导个性化答疑与练习推荐）
    from app.models.business_loop import WeaknessDiagnostic

    diags = db.scalars(
        select(WeaknessDiagnostic)
        .where(
            WeaknessDiagnostic.user_id == user_id,
            WeaknessDiagnostic.status != "treated",
        )
        .order_by(WeaknessDiagnostic.id.desc())
        .limit(3)
    ).all()
    if diags:
        weak_text = "；".join(
            "「{}」掌握度 {} 分".format(d.kp_name, d.mastery_score) for d in diags
        )
        context_parts.append(f"用户待攻克弱点：{weak_text}。请主动给出攻克建议与辅导。")
    else:
        context_parts.append("用户当前无明显弱点诊断，按计划推进即可。")

    return (
        "请结合该进度回答，若问题超出其当前阶段可先给概念解释再给进阶方向。\n"
        + "\n".join(context_parts)
    )


def build_tutor_prompt(
    question: str,
    hits: List[Dict[str, Any]],
    learning_context: str,
    history: List[Dict[str, str]],
) -> Tuple[str, str]:
    """组装 system + user prompt（引用约束由系统提示强制）。"""
    if not hits:
        evidence = "【检索结果】知识库中未检索到与问题相关的文档片段。"
        instruction = (
            "你不得编造答案。请明确告知用户知识库中暂无相关内容，"
            "并给出可替代的建议（提问关键词、上传文档或换一种问法）。"
        )
    else:
        parts = []
        for h in hits:
            parts.append(
                "证据[分块{}｜文档《{}》｜来源{}｜相似度{}]:\n{}".format(
                    h["chunk_id"], h["doc_title"], h["source"] or "未知",
                    h["score"], h["content"],
                )
            )
        evidence = "【知识库检索结果（按相关度排序）】\n" + "\n\n".join(parts)
        instruction = (
            "请基于上述证据回答用户问题。回答必须引用证据（标注文档名称与分块编号），"
            "不得编造证据之外的内容；若证据不足以回答，请明确说明并引导补充。"
        )

    system_prompt = (
        "你是 SkillQuest AI 的 AI 导师（Tutor Agent），负责基于企业内部知识库答疑。\n"
        "规则：\n"
        "1. 答案必须基于证据，且必须包含引用来源（证据文档名/分块ID）。\n"
        "2. 检索不到时明确说明『知识库暂无相关内容』，绝不编造。\n"
        "3. 结合用户当前学习进度作答（学习进度已提供）。\n"
        "4. 输出必须是 JSON，字段：answer(回答正文,可含\"\\n\"换行), "
        "references(引用数组), sufficient(布尔,证据是否足够)。\n"
        f"【当前学习进度】\n{learning_context}\n"
    )

    user_prompt = (
        f"用户问题：{question}\n\n{evidence}\n\n{instruction}\n\n"
        "【最近对话】\n" + ("\n".join(
            f"{m['role']}: {m['content'][:200]}" for m in history[-6:]
        ) if history else "（无）")
    )
    return system_prompt, user_prompt


# -------------------------------------------------------------------- #
# 推荐练习（关联技能节点的练习类资源，规则排序）
# -------------------------------------------------------------------- #
def recommend_practices(
    db: Session, skill_node_id: Optional[int], limit: int = 3
) -> List[Dict[str, Any]]:
    """按技能节点推荐练习资源（exercise 类型，来自 learning_resources）。

    规则：优先直接匹配该技能的练习；无匹配则取任意练习作为泛练。
    返回 [{resource_id, title, type, duration, difficulty, reason}]。
    """
    from app.models.learning_path import (
        RESOURCE_EXERCISE,
        LearningResource,
    )

    if skill_node_id:
        rows = db.scalars(
            select(LearningResource)
            .where(
                LearningResource.skill_node_id == skill_node_id,
                LearningResource.type == RESOURCE_EXERCISE,
            )
            .order_by(LearningResource.id.desc())
            .limit(limit)
        ).all()
        if rows:
            return [
                {
                    "resource_id": r.id,
                    "title": r.title,
                    "type": r.type,
                    "duration": r.duration,
                    "difficulty": r.difficulty,
                    "reason": "与你正在学习的技能直接相关，趁热练习巩固。",
                }
                for r in rows
            ]
    # 泛练兜底
    rows = db.scalars(
        select(LearningResource)
        .where(LearningResource.type == RESOURCE_EXERCISE)
        .order_by(LearningResource.id.asc())
        .limit(limit)
    ).all()
    return [
        {
            "resource_id": r.id,
            "title": r.title,
            "type": r.type,
            "duration": r.duration,
            "difficulty": r.difficulty,
            "reason": "通用练习，可检验概念理解。",
        }
        for r in rows
    ]


def map_related_skills(
    db: Session, hits: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """从检索命中提取关联知识点（skill_node_id 去重 + 名称）。"""
    from app.models.skill import SkillNode

    node_ids: List[int] = []
    seen: set = set()
    for h in hits:
        sid = h.get("skill_node_id")
        if sid and sid not in seen:
            seen.add(sid)
            node_ids.append(sid)
    out: List[Dict[str, Any]] = []
    for sid in node_ids:
        node = db.get(SkillNode, sid)
        if node:
            out.append({"skill_node_id": sid, "name": node.name})
    return out