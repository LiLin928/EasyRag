# Phase1 RAG 检索管线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development / executing-plans. Steps use `- [ ]` tracking.

**Goal:** 实现统一检索管线——query 向量 → 向量检索(pgvector) + 全文检索(pg_trgm) → RRF 融合 → 条件 Rerank → 可选结构导航缩域，并包装为 LangChain `HybridRetriever(BaseRetriever)` 供 chat/agent/workflow 复用。

**Architecture:** 纯函数/异步函数分层：`vector_search`/`fulltext_search`（原生 SQL）→ `rrf_merge`（纯函数）→ `reranker`（条件触发，调 Plan 2 的 ApiReranker）→ `navigator`（nav_embedding 缩域）→ `pipeline`（编排）→ `HybridRetriever`（LangChain 适配）。参数来自 Plan 2 的 `get_scene_config`。

**Tech Stack:** pgvector（`<=>` 余弦）、pg_trgm（`%`/`similarity`）、LangChain 1.X（BaseRetriever/Document）、Plan 2 的 build_embeddings/ApiReranker/get_scene_config。

**前置：** Plan 1/2/3 完成（chunks 表 + embedding + ApiReranker + scenes）。

---

## File Structure

```
backend/app/core/retrieval/
├── __init__.py
├── vector_search.py        # Task 1
├── fulltext_search.py      # Task 2
├── rrf_merge.py            # Task 3
├── reranker.py             # Task 4
├── navigator.py            # Task 5
├── pipeline.py             # Task 6
└── hybrid_retriever.py     # Task 7
backend/app/api/v2/retrieval.py   # Task 8（/navigate /search 调试）
backend/tests/test_retrieval_*.py
```

---

### Task 1: vector_search（pgvector）

**Files:** `backend/app/core/retrieval/vector_search.py` · Test: `tests/test_vector_search.py`

- [ ] **Step 1: 写失败测试**（用真实 chunks 数据）

```python
# tests/test_vector_search.py
import pytest
from app.core.retrieval.vector_search import search
from app.db.session import async_session, engine
from sqlalchemy import text

@pytest.mark.asyncio
async def test_vector_search_returns_scored():
    # 插入一条带向量的 chunk（维度 1024）
    async with async_session() as s:
        await s.execute(text("DELETE FROM chunks"))
        emb = str([0.1]*1024)
        await s.execute(text("INSERT INTO chunks (id, document_id, kb_id, content, content_search, page_number, seq, embedding) VALUES (gen_random_uuid(), gen_random_uuid(), 'kb1', '叉车参数', '叉车参数', 1, 0, :emb::vector)"), {"emb": emb})
        await s.commit()
    hits = await search(q_emb=[0.1]*1024, kb_ids=["kb1"], doc_ids=None, scope=None, top_k=5)
    assert len(hits) == 1
    assert "score" in hits[0] and "content" in hits[0]
```

- [ ] **Step 2: 实现 `vector_search.py`**

```python
from sqlalchemy import text
from app.db.session import async_session

SQL = """
SELECT id, document_id, content, clause_title, section_path, page_number,
       1 - (embedding <=> :emb::vector) AS score
FROM chunks
WHERE kb_id = ANY(:kb_ids)
  AND (:doc_ids::uuid[] IS NULL OR document_id = ANY(:doc_ids::uuid[]))
  AND (:scope::uuid[] IS NULL OR id = ANY(:scope::uuid[]))
  AND embedding IS NOT NULL
ORDER BY embedding <=> :emb::vector
LIMIT :k
"""

async def search(q_emb: list[float], kb_ids: list[str], doc_ids: list[str] | None,
                 scope: list[str] | None, top_k: int) -> list[dict]:
    async with async_session() as s:
        rows = (await s.execute(text(SQL), {
            "emb": str(q_emb), "kb_ids": kb_ids,
            "doc_ids": doc_ids, "scope": scope, "k": top_k,
        })).mappings().all()
    return [dict(r) for r in rows]
```

- [ ] **Step 3: 测试通过** → `pytest tests/test_vector_search.py -v` PASS

- [ ] **Step 4: Commit** `git add app/core/retrieval/vector_search.py tests/test_vector_search.py && git commit -m "feat(retrieval): pgvector cosine search"`

---

### Task 2: fulltext_search（pg_trgm）

**Files:** `backend/app/core/retrieval/fulltext_search.py` · Test: `tests/test_fulltext_search.py`

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.asyncio
async def test_fulltext_search():
    from app.core.retrieval.fulltext_search import search
    hits = await search(query="叉车", kb_ids=["kb1"], doc_ids=None, scope=None, top_k=5)
    assert isinstance(hits, list)
    assert all("score" in h for h in hits)
```

- [ ] **Step 2: 实现 `fulltext_search.py`**

```python
from sqlalchemy import text
from app.db.session import async_session

SQL = """
SELECT id, document_id, content, clause_title, section_path, page_number,
       similarity(content_search, :q) AS score
FROM chunks
WHERE kb_id = ANY(:kb_ids)
  AND (:doc_ids::uuid[] IS NULL OR document_id = ANY(:doc_ids::uuid[]))
  AND (:scope::uuid[] IS NULL OR id = ANY(:scope::uuid[]))
  AND content_search % :q
ORDER BY score DESC
LIMIT :k
"""

async def search(query: str, kb_ids: list[str], doc_ids: list[str] | None,
                 scope: list[str] | None, top_k: int) -> list[dict]:
    async with async_session() as s:
        rows = (await s.execute(text(SQL), {
            "q": query, "kb_ids": kb_ids, "doc_ids": doc_ids, "scope": scope, "k": top_k,
        })).mappings().all()
    return [dict(r) for r in rows]
```

- [ ] **Step 3: 测试通过** → PASS

- [ ] **Step 4: Commit** `git commit -m "feat(retrieval): pg_trgm fulltext search"`

---

### Task 3: rrf_merge（纯函数）

**Files:** `backend/app/core/retrieval/rrf_merge.py` · Test: `tests/test_rrf.py`

- [ ] **Step 1: 写失败测试**

```python
from app.core.retrieval.rrf_merge import merge

def test_merge_rank_fusion():
    vec = [{"id": "a", "content": "A"}, {"id": "b", "content": "B"}]
    kw = [{"id": "b", "content": "B"}, {"id": "c", "content": "C"}]
    fused = merge(vec, kw, w_vec=0.7, w_kw=0.3, k=60)
    ids = [f["id"] for f in fused]
    assert ids[0] == "b"          # 两路都命中，RRF 最高
    assert set(ids) == {"a", "b", "c"}
    assert "rrf" in fused[0]

def test_empty():
    assert merge([], []) == []
```

- [ ] **Step 2: 实现 `rrf_merge.py`**

```python
def merge(vec_hits: list[dict], kw_hits: list[dict], w_vec: float = 0.7, w_kw: float = 0.3, k: int = 60) -> list[dict]:
    scores: dict[str, dict] = {}
    for rank, h in enumerate(vec_hits):
        hid = str(h["id"])
        if hid not in scores:
            scores[hid] = {**h, "id": hid, "rrf": 0.0, "vector_rank": rank + 1}
        scores[hid]["rrf"] += w_vec / (k + rank + 1)
    for rank, h in enumerate(kw_hits):
        hid = str(h["id"])
        if hid not in scores:
            scores[hid] = {**h, "id": hid, "rrf": 0.0, "fulltext_rank": rank + 1}
        scores[hid]["rrf"] += w_kw / (k + rank + 1)
    return sorted(scores.values(), key=lambda x: x["rrf"], reverse=True)
```

- [ ] **Step 3: 测试通过** → PASS · **Step 4: Commit** `git commit -m "feat(retrieval): rrf fusion"`

---

### Task 4: reranker（条件触发 + ApiReranker 集成）

**Files:** `backend/app/core/retrieval/reranker.py` · Test: `tests/test_reranker.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from unittest.mock import AsyncMock
from app.core.retrieval.reranker import should_rerank, rerank

def test_should_rerank_when_scores_close():
    fused = [{"id": "a", "rrf": 0.032}, {"id": "b", "rrf": 0.030}]
    assert should_rerank(fused, threshold=0.02) is True     # 0.002 < 0.02

def test_should_not_rerank_when_clear():
    fused = [{"id": "a", "rrf": 0.10}, {"id": "b", "rrf": 0.02}]
    assert should_rerank(fused, threshold=0.02) is False    # 0.08 >= 0.02

@pytest.mark.asyncio
async def test_rerank_reorders():
    fused = [{"id": "a", "content": "A", "rrf": 0.03}, {"id": "b", "content": "B", "rrf": 0.032}]
    rk = AsyncMock(); rk.rerank = AsyncMock(return_value=[(1, 0.9), (0, 0.5)])  # b 胜出
    out = await rerank("q", fused, top_n=2, reranker=rk)
    assert out[0]["id"] == "b"
    assert "rerank_score" in out[0]
```

- [ ] **Step 2: 实现 `reranker.py`**

```python
def should_rerank(fused: list[dict], threshold: float) -> bool:
    if len(fused) < 2:
        return False
    return (fused[0]["rrf"] - fused[1]["rrf"]) < threshold


async def rerank(query: str, fused: list[dict], top_n: int, reranker) -> list[dict]:
    docs = [f["content"] for f in fused]
    ranked = await reranker.rerank(query, docs, top_n)      # [(orig_idx, score)]
    return [{**fused[i], "rerank_score": sc} for i, sc in ranked]
```

- [ ] **Step 3: 测试通过** → PASS · **Step 4: Commit** `git commit -m "feat(retrieval): conditional rerank"`

---

### Task 5: navigator（结构导航缩域）

**Files:** `backend/app/core/retrieval/navigator.py` · Test: `tests/test_navigator.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.core.retrieval.navigator import navigate

@pytest.mark.asyncio
async def test_navigate_returns_anchors():
    with patch("app.core.retrieval.navigator._fetch_nodes", AsyncMock(return_value=[
        {"id": "n1", "document_id": "d1", "title": "4.2 验收", "page_start": 28, "page_end": 30, "level": 2, "score": 0.91},
        {"id": "n2", "document_id": "d1", "title": "4.3 交付", "page_start": 31, "page_end": 33, "level": 2, "score": 0.50},
    ])), patch("app.core.retrieval.navigator._chunks_in_pages", AsyncMock(return_value=["c1","c2"])):
        r = await navigate(q_emb=[0.1]*8, doc_ids=["d1"], top_k=2, threshold=0.15)
    assert r["scoped"] is True              # 0.91-0.50=0.41 >= 0.15
    assert r["scope_chunk_ids"] == ["c1","c2"]
    assert r["anchors"][0]["title"] == "4.2 验收"
```

- [ ] **Step 2: 实现 `navigator.py`**

```python
from sqlalchemy import text
from app.db.session import async_session

_NODE_SQL = """
SELECT id, document_id, title, page_start, page_end, level,
       1 - (nav_embedding <=> :emb::vector) AS score
FROM doc_tree_nodes
WHERE document_id = ANY(:doc_ids::uuid[]) AND level > 0 AND nav_embedding IS NOT NULL
ORDER BY nav_embedding <=> :emb::vector LIMIT :k
"""


async def _fetch_nodes(q_emb, doc_ids, top_k):
    async with async_session() as s:
        rows = (await s.execute(text(_NODE_SQL), {"emb": str(q_emb), "doc_ids": doc_ids, "k": top_k})).mappings().all()
    return [dict(r) for r in rows]


async def _chunks_in_pages(ranges: list[tuple]) -> list[str]:
    """ranges: [(doc_id, page_start, page_end), ...] → 收集这些页码范围内的 chunk id"""
    ids: list[str] = []
    async with async_session() as s:
        for doc_id, ps, pe in ranges:
            rows = (await s.execute(text(
                "SELECT id::text FROM chunks WHERE document_id = :d AND page_number BETWEEN :ps AND :pe"),
                {"d": doc_id, "ps": ps or 1, "pe": pe or 9999})).mappings().all()
            ids.extend(r["id"] for r in rows)
    return ids


async def navigate(q_emb: list[float], doc_ids: list[str], top_k: int, threshold: float) -> dict:
    nodes = await _fetch_nodes(q_emb, doc_ids, top_k)
    if not nodes:
        return {"scoped": False, "anchors": [], "scope_chunk_ids": None, "confidence": 0.0}
    top = nodes[0]
    second = nodes[1] if len(nodes) > 1 else None
    confidence = float(top["score"])
    margin = confidence - (float(second["score"]) if second else 1.0)
    scoped = margin >= threshold
    scope = None
    if scoped:
        ranges = [(str(n["document_id"]), n["page_start"], n["page_end"]) for n in nodes[:top_k]]
        scope = await _chunks_in_pages(ranges)
    anchors = [{"node_id": str(n["id"]), "title": n["title"], "confidence": float(n["score"])} for n in nodes[:top_k]]
    return {"scoped": scoped, "anchors": anchors, "scope_chunk_ids": scope, "confidence": confidence}
```

- [ ] **Step 3: 测试通过** → PASS · **Step 4: Commit** `git commit -m "feat(retrieval): embedding navigator with page-scope"`

---

### Task 6: retrieval pipeline（统一编排）

**Files:** `backend/app/core/retrieval/pipeline.py` · Test: `tests/test_pipeline.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.core.retrieval.pipeline import RetrievalPipeline

@pytest.mark.asyncio
async def test_pipeline_orchestrates(monkeypatch):
    p = RetrievalPipeline(scene_config=AsyncMock(vector_top_k=10, trgm_top_k=10, top_k=5,
        rerank_enabled=False, rerank_threshold=0.02, navigation_enabled=False,
        vector_weight=0.7, keyword_weight=0.3, rrf_k=60, rerank_top_n=5))
    with patch.object(p, "_embed_query", AsyncMock(return_value=[0.1]*8)), \
         patch("app.core.retrieval.pipeline.vector_search.search", AsyncMock(return_value=[{"id":"a","content":"A"}])), \
         patch("app.core.retrieval.pipeline.fulltext_search.search", AsyncMock(return_value=[])):
        r = await p.search(query="q", doc_ids=["d1"], top_k=5)
    assert len(r.chunks) >= 1
    assert r.references is not None
```

- [ ] **Step 2: 实现 `pipeline.py`**

```python
from dataclasses import dataclass, field
from app.providers.langchain_factory import build_embeddings
from app.core.retrieval import vector_search, fulltext_search, rrf_merge, reranker, navigator
from app.core.reference_builder import build_references   # Plan 5 提供；此处先占位接口


@dataclass
class RetrievalResult:
    chunks: list[dict] = field(default_factory=list)
    references: list[dict] = field(default_factory=list)
    nav_info: dict | None = None
    mode: str = "hybrid"
    rerank_triggered: bool = False


class RetrievalPipeline:
    def __init__(self, scene_config):
        self.cfg = scene_config
        self.last_result: RetrievalResult | None = None

    async def _embed_query(self, query: str) -> list[float]:
        emb = await build_embeddings()
        return await emb.aembed_query(query)

    async def _reranker(self):
        from app.services.settings_service import get_default_model
        from app.providers.rerank.api_reranker import ApiReranker
        from app.security.crypto import decrypt
        cfg = await get_default_model("rerank", "rerank") or await get_default_model("rerank")
        if not cfg:
            return None
        return ApiReranker(url=cfg.url, api_key=decrypt(cfg.api_key_enc) if cfg.api_key_enc else "", model=cfg.name)

    async def search(self, query: str, doc_ids: list[str], top_k: int = 5, enable_nav: bool = True) -> RetrievalResult:
        cfg = self.cfg
        q_emb = await self._embed_query(query)

        scope = None
        nav_info = None
        if enable_nav and cfg.navigation_enabled:
            nav_info = await navigator.navigate(q_emb, doc_ids, top_k=5, threshold=cfg.nav_confidence_threshold)
            if nav_info["scoped"]:
                scope = nav_info["scope_chunk_ids"]

        vec_hits = await vector_search.search(q_emb, kb_ids=[], doc_ids=doc_ids, scope=scope, top_k=cfg.vector_top_k)
        kw_hits = await fulltext_search.search(query, kb_ids=[], doc_ids=doc_ids, scope=scope, top_k=cfg.trgm_top_k)
        fused = rrf_merge.merge(vec_hits, kw_hits, cfg.vector_weight, cfg.keyword_weight, cfg.rrf_k)

        triggered = reranker.should_rerank(fused, cfg.rerank_threshold) and cfg.rerank_enabled
        if triggered:
            rk = await self._reranker()
            if rk:
                fused = await reranker.rerank(query, fused, cfg.rerank_top_n, rk)

        top = fused[:top_k]
        refs = build_references(top)         # 轻量引用（Plan 5 Task 实现；先返回简单结构）
        result = RetrievalResult(chunks=top, references=refs, nav_info=nav_info,
                                  mode="nav" if scope else "hybrid", rerank_triggered=triggered)
        self.last_result = result
        return result
```

> 注：`build_references` 与 `reference_builder.py` 在 Plan 5 Task 实现；若 Plan 5 未到，先在本 Task 创建一个最小 `reference_builder.py` 返回 `[{ref_id, content_preview, score}]`，Plan 5 再扩展为完整字段。

- [ ] **Step 3: 创建最小 `backend/app/core/reference_builder.py`（Plan 5 会扩展）**

```python
def build_references(chunks: list[dict]) -> list[dict]:
    return [{"ref_id": f"r{i}", "element_id": str(c.get("id")), "content_preview": (c.get("content") or "")[:80],
             "score": c.get("rerank_score", c.get("rrf", c.get("score", 0))), "type": "text"} for i, c in enumerate(chunks)]
```

- [ ] **Step 4: 测试通过** → PASS · **Step 5: Commit** `git commit -m "feat(retrieval): unified pipeline + reference builder"`

---

### Task 7: HybridRetriever（LangChain BaseRetriever）

**Files:** `backend/app/core/retrieval/hybrid_retriever.py` · Test: `tests/test_hybrid_retriever.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from unittest.mock import AsyncMock, patch
from langchain_core.documents import Document
from app.core.retrieval.hybrid_retriever import HybridRetriever

@pytest.mark.asyncio
async def test_retriever_returns_documents():
    r = HybridRetriever(doc_ids=["d1"], scene_config=AsyncMock(navigation_enabled=False))
    with patch.object(r._pipeline, "search", AsyncMock(return_value=type("R",(),{
        "chunks":[{"id":"c1","content":"hi","document_id":"d1","clause_title":"t","page_number":1}],
        "references":[],"nav_info":None,"mode":"hybrid","rerank_triggered":False}()) )):
        docs = await r.ainvoke("q")
    assert len(docs) == 1 and isinstance(docs[0], Document)
    assert docs[0].metadata["chunk_id"] == "c1"
```

- [ ] **Step 2: 实现 `hybrid_retriever.py`**

```python
from typing import List
from pydantic import PrivateAttr
from langchain_core.callbacks import AsyncCallbackManagerForRetrieverRun
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from app.core.retrieval.pipeline import RetrievalPipeline, RetrievalResult


class HybridRetriever(BaseRetriever):
    doc_ids: List[str]
    scene_config: object
    top_k: int = 5
    enable_nav: bool = True
    _pipeline: RetrievalPipeline = PrivateAttr()
    _last_result: RetrievalResult | None = PrivateAttr(default=None)

    def __init__(self, **data):
        super().__init__(**data)
        self._pipeline = RetrievalPipeline(scene_config=self.scene_config)

    @property
    def last_result(self):
        return self._pipeline.last_result

    def _get_relevant_documents(self, query, *, run_manager): raise NotImplementedError("use ainvoke")

    async def _aget_relevant_documents(self, query: str, *, run_manager: AsyncCallbackManagerForRetrieverRun) -> List[Document]:
        result = await self._pipeline.search(query, self.doc_ids, self.top_k, self.enable_nav)
        self._last_result = result
        return [Document(page_content=c.get("content", ""), metadata={
            "chunk_id": str(c.get("id")), "doc_id": str(c.get("document_id")),
            "node_title": c.get("clause_title"), "page_number": c.get("page_number", 1),
            "section_path": c.get("section_path"), "score": c.get("rerank_score", c.get("rrf", 0)),
        }) for c in result.chunks]
```

- [ ] **Step 3: 测试通过** → PASS · **Step 4: Commit** `git commit -m "feat(retrieval): HybridRetriever (BaseRetriever)"`

---

### Task 8: /navigate + /search 调试 API + 冒烟

**Files:** `backend/app/api/v2/retrieval.py` · Modify `main.py` · Test: `tests/test_retrieval_api.py`

- [ ] **Step 1: 实现 `api/v2/retrieval.py`**

```python
from fastapi import APIRouter, Depends, Body
from pydantic import BaseModel
from app.api.deps import get_current_user
from app.api.response import ok
from app.providers.langchain_factory import build_embeddings
from app.core.retrieval import navigator, vector_search, fulltext_search, rrf_merge, reranker
from app.core.scenes import get_scene_config

router = APIRouter(tags=["retrieval"])

class NavReq(BaseModel):
    question: str
    document_ids: list[str]
    top_n: int = 3

@router.post("/navigate")
async def navigate_api(req: NavReq, me=Depends(get_current_user)):
    emb = await build_embeddings()
    q_emb = await emb.aembed_query(req.question)
    cfg = await get_scene_config("general")
    r = await navigator.navigate(q_emb, req.document_ids, req.top_n, cfg.nav_confidence_threshold)
    return ok({"anchors": r["anchors"], "fallback_used": not r["scoped"]})

class SearchReq(BaseModel):
    question: str
    document_ids: list[str]
    top_k: int = 5
    enable_rerank: bool = True

@router.post("/search")
async def search_api(req: SearchReq, me=Depends(get_current_user)):
    emb = await build_embeddings()
    q_emb = await emb.aembed_query(req.question)
    v = await vector_search.search(q_emb, [], req.document_ids, None, 20)
    k = await fulltext_search.search(req.question, [], req.document_ids, None, 20)
    fused = rrf_merge.merge(v, k)
    triggered = False
    if req.enable_rerank and reranker.should_rerank(fused, 0.02):
        triggered = True
    return ok({"results": fused[:req.top_k], "rerank_triggered": triggered})
```

- [ ] **Step 2: 挂载** `app.include_router(retrieval.router, prefix=settings.api_prefix)`

- [ ] **Step 3: 写测试**（mock embeddings，验证返回结构）

```python
@pytest.mark.asyncio
async def test_search_api_shape():
    from unittest.mock import AsyncMock, patch
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    fake = AsyncMock(); fake.aembed_query = AsyncMock(return_value=[0.1]*8)
    with patch("app.api.v2.retrieval.build_embeddings", AsyncMock(return_value=fake)), \
         patch("app.api.v2.retrieval.vector_search.search", AsyncMock(return_value=[])), \
         patch("app.api.v2.retrieval.fulltext_search.search", AsyncMock(return_value=[])):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            # 需带 token（省略登录，用 admin fixture）
            r = await c.post("/api/v2/search", json={"question":"q","document_ids":["d1"]})
    assert r.json()["code"] == 0
```

- [ ] **Step 4: 全量测试 + Commit**

```bash
cd backend && pytest -v
git add app/api/v2/retrieval.py app/main.py tests/ && git commit -m "feat(retrieval): /navigate /search debug apis + smoke"
```

---

## Plan 4 完成标志
- ✅ vector_search（pgvector 余弦）+ fulltext_search（pg_trgm）+ rrf_merge + 条件 reranker + navigator（页码缩域）
- ✅ RetrievalPipeline 统一编排 + RetrievalResult
- ✅ HybridRetriever（LangChain BaseRetriever），供 Plan 5 chat 复用
- ✅ `/navigate` `/search` 调试 API

**下一步：** Plan 5 chat（LangChain 1.X）SSE——用 HybridRetriever + 查询改写 + 流式生成。

*— 计划结束 —*