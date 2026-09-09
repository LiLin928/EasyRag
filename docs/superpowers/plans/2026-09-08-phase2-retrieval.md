# Phase 2.5 检索引擎增强实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现混合检索引擎，支持向量检索、关键词检索、重排序、导航式检索和完整的检索测试功能

**Architecture:** 基于 pgvector 向量检索 + pg_trgm 全文检索，使用 RRF 融合算法合并结果，集成 LangChain Reranker 进行重排序

**Tech Stack:** pgvector, pg_trgm, LangChain, Reranker, ARQ

**关联文档:**
- 后端设计方案: `docs/backend-plans/后端开发设计方案.md`
- API匹配报告: `docs/API匹配分析报告.md`
- Phase 1 计划: `2026-09-08-phase1-completion.md`

---

## 概览

**当前状态:**
- 检索基础: 0%
- 检索测试: 0%
- 知识库核心: 100%

**目标:**
- 混合检索: 100%
- 重排序: 100%
- 导航式检索: 100%
- 检索测试运行: 100%

**预计任务数:** 20
**预计时间:** 4-5天

---

## 架构设计

### 检索流程

```
用户查询
  ↓
向量化（Embedding）
  ↓
┌─────────┬─────────┐
│ 向量检索 │ 关键词检索 │
│ pgvector │ pg_trgm   │
└─────────┴─────────┘
  ↓         ↓
  └────┬────┘
       ↓
    RRF 融合
       ↓
    重排序（Rerank）
       ↓
    导航范围过滤
       ↓
    返回 Top-K 结果
```

### 核心概念

1. **混合检索**: 向量检索 + 关键词检索
2. **RRF融合**: Reciprocal Rank Fusion 算法
3. **重排序**: Reranker 模型二次排序
4. **导航式检索**: 基于文档树的智能范围过滤
5. **检索测试**: 自动化检索质量评估

---

## 文件结构规划

### 新增文件
```
backend/app/
├── core/
│   └── retrieval/
│       ├── __init__.py
│       ├── hybrid_search.py      # 混合检索引擎
│       ├── rrf.py                # RRF 融合算法
│       ├── reranker.py           # 重排序器
│       ├── navigation.py         # 导航式检索
│       └── embedder.py           # Embedding 封装
├── services/
│   ├── retrieval_service.py      # 检索服务
│   └── retrieval_test_service.py # 检索测试服务
├── api/v2/
│   ├── retrieval.py              # 检索接口
│   └── retrieval_testing.py      # 检索测试接口（扩展）
├── models/
│   ├── retrieval_test_run.py     # 测试运行 ORM
│   └── retrieval_test_case.py    # 测试用例 ORM
├── schemas/
│   └── retrieval.py              # 检索 Schema
└── worker/
    └── retrieval_test_worker.py  # 检索测试 ARQ 任务

backend/tests/
├── test_hybrid_search.py
├── test_reranker.py
├── test_navigation.py
└── test_retrieval_testing.py
```

---

## Task 1: Embedding 模型封装

**优先级:** P0
**预计时间:** 1小时

### Step 1.1: 创建 Embedding 封装

- [ ] **实现 Embedding 服务**

Create: `backend/app/core/retrieval/embedder.py`

```python
"""Embedding 模型封装。"""
from typing import List
from langchain_openai import OpenAIEmbeddings
from langchain_ollama import OllamaEmbeddings
from app.providers.langchain_factory import build_embeddings

class Embedder:
    """Embedding 模型封装类。"""

    def __init__(self, model_id: str):
        """初始化 Embedder。

        Args:
            model_id: 模型配置ID
        """
        self.model_id = model_id
        self._embeddings = None

    async def get_embeddings(self) -> OpenAIEmbeddings:
        """获取 Embeddings 实例。"""
        if self._embeddings is None:
            self._embeddings = await build_embeddings(self.model_id)
        return self._embeddings

    async def embed_query(self, text: str) -> List[float]:
        """向量化单个查询。

        Args:
            text: 查询文本

        Returns:
            向量（list of float）
        """
        embeddings = await self.get_embeddings()
        return await embeddings.aembed_query(text)

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量向量化文档。

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        embeddings = await self.get_embeddings()
        return await embeddings.aembed_documents(texts)
```

### Step 1.2: 编写测试

- [ ] **测试 Embedder**

Create: `backend/tests/test_embedder.py`

```python
"""Embedder 测试。"""
import pytest
from app.core.retrieval.embedder import Embedder

@pytest.mark.asyncio
async def test_embed_query():
    """测试单条查询向量化。"""
    embedder = Embedder("model-embedding")
    vector = await embedder.embed_query("测试查询")

    assert isinstance(vector, list)
    assert len(vector) == 1024  # 假设维度为1024
    assert all(isinstance(v, float) for v in vector)
```

### Step 1.3: 提交代码

- [ ] **提交 Embedder 实现**

```bash
git add backend/app/core/retrieval/embedder.py backend/tests/test_embedder.py
git commit -m "feat(core): add embedding wrapper"
```

---

## Task 2: 混合检索引擎

**优先级:** P0
**预计时间:** 3小时

### Step 2.1: 定义检索 Schema

- [ ] **创建检索相关 Schema**

Create: `backend/app/schemas/retrieval.py`

```python
"""检索 Schema。"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class RetrievalRequest(BaseModel):
    """检索请求。"""
    query: str
    kb_id: str
    top_k: int = 5
    method: str = "hybrid"  # vector/keyword/hybrid
    vector_top_k: int = 20
    keyword_top_k: int = 20
    vector_weight: float = 0.7
    keyword_weight: float = 0.3
    similarity_threshold: float = 0.3
    rerank_enabled: bool = True
    rerank_top_n: int = 10
    navigation_enabled: bool = True
    metadata_filters: Dict[str, Any] = {}

class RetrievalCandidate(BaseModel):
    """检索候选项。"""
    rank: int
    chunk_id: str
    document_id: str
    document_name: str
    content: str
    page_number: int
    vector_score: float
    keyword_score: float
    final_score: float
    metadata: Dict[str, Any]

class RetrievalResult(BaseModel):
    """检索结果。"""
    query: str
    candidates: List[RetrievalCandidate]
    total: int
    retrieval_time_ms: int
```

### Step 2.2: 实现向量检索

- [ ] **实现 pgvector 向量检索**

Create: `backend/app/core/retrieval/hybrid_search.py`

```python
"""混合检索引擎。"""
from typing import List, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector
from app.models.chunk import Chunk
from app.core.retrieval.embedder import Embedder

class VectorSearch:
    """向量检索器。"""

    def __init__(self, embedder: Embedder):
        self.embedder = embedder

    async def search(
        self,
        session: AsyncSession,
        kb_id: str,
        query_vector: List[float],
        top_k: int = 20,
        filters: Dict[str, Any] = None
    ) -> List[Dict]:
        """执行向量检索。

        Args:
            session: 数据库会话
            kb_id: 知识库ID
            query_vector: 查询向量
            top_k: 返回数量
            filters: 元数据过滤条件

        Returns:
            检索结果列表
        """
        # 构建查询
        q = select(Chunk).where(
            and_(
                Chunk.kb_id == kb_id,
                Chunk.enabled == True,
                Chunk.embedding.isnot(None)
            )
        )

        # 元数据过滤
        if filters:
            for key, value in filters.items():
                q = q.where(Chunk.metadata[key].astext == str(value))

        # 向量相似度计算（余弦距离）
        q = q.order_by(
            Chunk.embedding.cosine_distance(query_vector)
        ).limit(top_k)

        # 执行查询
        results = await session.execute(q)
        chunks = results.scalars().all()

        # 格式化结果
        candidates = []
        for idx, chunk in enumerate(chunks):
            # 计算相似度分数（pgvector返回的是距离，需要转换为分数）
            # 余弦距离 = 1 - 余弦相似度
            distance = await session.scalar(
                select(Chunk.embedding.cosine_distance(query_vector)).where(Chunk.id == chunk.id)
            )
            similarity = 1 - distance if distance is not None else 0

            candidates.append({
                "rank": idx + 1,
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "document_name": chunk.document_name,
                "content": chunk.content,
                "page_number": chunk.page_number,
                "vector_score": similarity,
                "keyword_score": 0.0,
                "metadata": chunk.metadata
            })

        return candidates
```

### Step 2.3: 实现关键词检索

- [ ] **实现 pg_trgm 全文检索**

Modify: `backend/app/core/retrieval/hybrid_search.py` (添加关键词检索)

```python
from sqlalchemy import or_, func

class KeywordSearch:
    """关键词检索器（基于 pg_trgm）。"""

    async def search(
        self,
        session: AsyncSession,
        kb_id: str,
        query: str,
        top_k: int = 20,
        filters: Dict[str, Any] = None
    ) -> List[Dict]:
        """执行关键词检索。

        使用 pg_trgm 三元组相似度进行模糊匹配。
        """
        # 构建查询
        q = select(Chunk).where(
            and_(
                Chunk.kb_id == kb_id,
                Chunk.enabled == True
            )
        )

        # 全文搜索：在 content 和 clause_title 中查找
        # 使用 pg_trgm 相似度
        q = q.where(
            or_(
                Chunk.content_search.op('%')(query),  # 包含查询词
                Chunk.clause_title.op('%')(query)
            )
        ).order_by(
            func.similarity(Chunk.content_search, query).desc()
        ).limit(top_k)

        results = await session.execute(q)
        chunks = results.scalars().all()

        candidates = []
        for idx, chunk in enumerate(chunks):
            # 计算关键词相似度
            similarity = await session.scalar(
                func.similarity(Chunk.content_search, query)
            )

            candidates.append({
                "rank": idx + 1,
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "document_name": chunk.document_name,
                "content": chunk.content,
                "page_number": chunk.page_number,
                "vector_score": 0.0,
                "keyword_score": similarity or 0,
                "metadata": chunk.metadata
            })

        return candidates
```

### Step 2.4: 实现 RRF 融合算法

- [ ] **实现 RRF 融合**

Create: `backend/app/core/retrieval/rrf.py`

```python
"""RRF (Reciprocal Rank Fusion) 融合算法。"""
from typing import List, Dict

def rrf_fusion(
    vector_results: List[Dict],
    keyword_results: List[Dict],
    k: int = 60
) -> List[Dict]:
    """RRF 融合向量检索和关键词检索结果。

    RRF公式: score(d) = sum(1 / (k + rank(d)))

    Args:
        vector_results: 向量检索结果
        keyword_results: 关键词检索结果
        k: RRF 参数（默认60）

    Returns:
        融合后的结果列表
    """
    # 构建文档ID到结果的映射
    doc_scores = {}

    # 累加向量检索分数
    for result in vector_results:
        doc_id = result["chunk_id"]
        rank = result["rank"]
        rrf_score = 1 / (k + rank)

        if doc_id not in doc_scores:
            doc_scores[doc_id] = {
                **result,
                "vector_score": result["vector_score"],
                "keyword_score": 0.0,
                "rrf_score": 0.0
            }
        doc_scores[doc_id]["rrf_score"] += rrf_score

    # 累加关键词检索分数
    for result in keyword_results:
        doc_id = result["chunk_id"]
        rank = result["rank"]
        rrf_score = 1 / (k + rank)

        if doc_id not in doc_scores:
            doc_scores[doc_id] = {
                **result,
                "vector_score": 0.0,
                "keyword_score": result["keyword_score"],
                "rrf_score": 0.0
            }
        doc_scores[doc_id]["rrf_score"] += rrf_score
        doc_scores[doc_id]["keyword_score"] = result["keyword_score"]

    # 按 RRF 分数排序
    sorted_results = sorted(
        doc_scores.values(),
        key=lambda x: x["rrf_score"],
        reverse=True
    )

    # 重新分配排名
    for idx, result in enumerate(sorted_results):
        result["rank"] = idx + 1

    return sorted_results
```

### Step 2.5: 编写混合检索测试

- [ ] **测试混合检索**

Create: `backend/tests/test_hybrid_search.py`

```python
"""混合检索测试。"""
import pytest
from app.core.retrieval.hybrid_search import VectorSearch, KeywordSearch
from app.core.retrieval.rrf import rrf_fusion
from app.core.retrieval.embedder import Embedder

@pytest.mark.asyncio
async def test_hybrid_search(db_session, mock_kb_with_chunks):
    """测试混合检索完整流程。"""
    kb_id = mock_kb_with_chunks

    # 1. 向量化查询
    embedder = Embedder("model-embedding")
    query_vector = await embedder.embed_query("知识库检索能力")

    # 2. 向量检索
    vector_searcher = VectorSearch(embedder)
    vector_results = await vector_searcher.search(
        db_session, kb_id, query_vector, top_k=20
    )

    assert len(vector_results) > 0
    assert all("vector_score" in r for r in vector_results)

    # 3. 关键词检索
    keyword_searcher = KeywordSearch()
    keyword_results = await keyword_searcher.search(
        db_session, kb_id, "知识库检索", top_k=20
    )

    assert len(keyword_results) > 0

    # 4. RRF 融合
    fused_results = rrf_fusion(vector_results, keyword_results, k=60)

    assert len(fused_results) > 0
    assert all("rrf_score" in r for r in fused_results)
    assert fused_results[0]["rank"] == 1
```

### Step 2.6: 提交代码

- [ ] **提交混合检索引擎**

```bash
git add backend/app/core/retrieval/ backend/app/schemas/retrieval.py backend/tests/test_hybrid_search.py
git commit -m "feat(core): implement hybrid search with RRF fusion"
```

---

## Task 3: 重排序器（Reranker）

**优先级:** P1
**预计时间:** 2小时

### Step 3.1: 实现 Reranker

- [ ] **创建 Reranker 封装**

Create: `backend/app/core/retrieval/reranker.py`

```python
"""重排序器。"""
from typing import List, Dict
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import FlashrankRerank
from app.providers.langchain_factory import build_reranker

class Reranker:
    """重排序器封装。"""

    def __init__(self, model_id: str):
        self.model_id = model_id
        self._reranker = None

    async def get_reranker(self):
        """获取 Reranker 实例。"""
        if self._reranker is None:
            self._reranker = await build_reranker(self.model_id)
        return self._reranker

    async def rerank(
        self,
        query: str,
        candidates: List[Dict],
        top_n: int = 10
    ) -> List[Dict]:
        """重排序候选结果。

        Args:
            query: 查询文本
            candidates: 候选结果列表
            top_n: 返回数量

        Returns:
            重排序后的结果
        """
        reranker = await self.get_reranker()

        # 构造文档列表
        documents = [
            {"page_content": c["content"], "metadata": c}
            for c in candidates
        ]

        # 执行重排序
        # 注意：LangChain的rerank接口可能因模型而异
        # 这里假设使用FlashrankRerank或类似实现
        results = await reranker.arerank(
            query=query,
            documents=documents,
            top_n=top_n
        )

        # 格式化结果
        reranked = []
        for idx, result in enumerate(results):
            metadata = result["metadata"]
            reranked.append({
                **metadata,
                "rank": idx + 1,
                "rerank_score": result.get("relevance_score", 0)
            })

        return reranked
```

### Step 3.2: 编写测试

- [ ] **测试 Reranker**

Create: `backend/tests/test_reranker.py`

```python
"""Reranker 测试。"""
import pytest
from app.core.retrieval.reranker import Reranker

@pytest.mark.asyncio
async def test_rerank():
    """测试重排序。"""
    reranker = Reranker("model-rerank")

    candidates = [
        {"content": "知识库支持向量检索", "metadata": {"doc_id": "1"}},
        {"content": "系统架构设计文档", "metadata": {"doc_id": "2"}},
        {"content": "检索能力包括混合检索", "metadata": {"doc_id": "3"}}
    ]

    results = await reranker.rerank(
        query="检索能力",
        candidates=candidates,
        top_n=3
    )

    assert len(results) == 3
    assert results[0]["rank"] == 1
    assert "rerank_score" in results[0]
    # 检索相关的文档应该排在前面
    assert "检索" in results[0]["content"]
```

### Step 3.3: 提交代码

- [ ] **提交 Reranker**

```bash
git add backend/app/core/retrieval/reranker.py backend/tests/test_reranker.py
git commit -m "feat(core): add reranker for retrieval"
```

---

## Task 4: 导航式检索

**优先级:** P1
**预计时间:** 2小时

**说明:** 导航式检索基于文档树结构，智能识别查询范围，提高检索精度。

### Step 4.1: 实现导航式检索

- [ ] **创建导航式检索模块**

Create: `backend/app/core/retrieval/navigation.py`

```python
"""导航式检索。"""
from typing import List, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.doc_tree_node import DocTreeNode

class NavigationSearch:
    """导航式检索。"""

    def __init__(
        self,
        confidence_threshold: float = 0.15,
        anchor_count: int = 3
    ):
        """初始化。

        Args:
            confidence_threshold: 置信度阈值（低于此值认为无法确定范围）
            anchor_count: 锚点数量（用于确定范围的节点数）
        """
        self.confidence_threshold = confidence_threshold
        self.anchor_count = anchor_count

    async def identify_scope(
        self,
        session: AsyncSession,
        kb_id: str,
        query: str,
        top_candidates: List[Dict]
    ) -> Optional[Dict]:
        """识别查询范围。

        通过分析Top-K结果所属的文档树节点，智能确定查询范围。

        Args:
            session: 数据库会话
            kb_id: 知识库ID
            query: 查询文本
            top_candidates: Top-K检索结果

        Returns:
            识别出的范围（包含节点ID和置信度），None表示无法确定
        """
        # 统计Top-K结果所属的节点
        node_scores = {}

        for candidate in top_candidates[:self.anchor_count]:
            node_id = candidate.get("metadata", {}).get("node_id")
            if not node_id:
                continue

            # 累加分数
            if node_id not in node_scores:
                node_scores[node_id] = 0
            node_scores[node_id] += candidate.get("final_score", 1)

        if not node_scores:
            return None

        # 找出得分最高的节点
        best_node_id = max(node_scores, key=node_scores.get)
        total_score = sum(node_scores.values())
        confidence = node_scores[best_node_id] / total_score

        # 置信度过低则不限定范围
        if confidence < self.confidence_threshold:
            return None

        # 查询节点信息
        node = await session.scalar(
            select(DocTreeNode).where(DocTreeNode.id == best_node_id)
        )

        if not node:
            return None

        return {
            "node_id": str(node.id),
            "node_title": node.title,
            "confidence": confidence,
            "filter_condition": {
                "section_path": node.section_path
            }
        }

    async def apply_navigation_filter(
        self,
        session: AsyncSession,
        kb_id: str,
        candidates: List[Dict],
        scope: Optional[Dict]
    ) -> List[Dict]:
        """应用导航范围过滤。

        Args:
            session: 数据库会话
            kb_id: 知识库ID
            candidates: 候选结果
            scope: 识别出的范围

        Returns:
            过滤后的结果
        """
        if not scope:
            # 无范围限定，直接返回
            return candidates

        # 过滤出属于该范围的文档
        # 注意：这里可以根据实际需求调整过滤逻辑
        # 例如：只返回该节点及其子节点下的chunk

        filter_condition = scope.get("filter_condition", {})
        filtered = []

        for candidate in candidates:
            metadata = candidate.get("metadata", {})
            # 检查是否属于该范围
            match = True
            for key, value in filter_condition.items():
                if metadata.get(key) != value:
                    match = False
                    break

            if match:
                candidate["navigation_scoped"] = True
                candidate["navigation_node"] = scope["node_title"]
                filtered.append(candidate)

        # 如果过滤后为空，返回原始结果
        return filtered if filtered else candidates
```

### Step 4.2: 编写测试

- [ ] **测试导航式检索**

Create: `backend/tests/test_navigation.py`

```python
"""导航式检索测试。"""
import pytest
from app.core.retrieval.navigation import NavigationSearch

@pytest.mark.asyncio
async def test_identify_scope(db_session, mock_kb_with_tree):
    """测试范围识别。"""
    nav_search = NavigationSearch(confidence_threshold=0.15)

    candidates = [
        {
            "content": "系统架构设计",
            "final_score": 0.95,
            "metadata": {"node_id": "n2-1", "section_path": "第二章/2.1 系统架构"}
        },
        {
            "content": "技术选型方案",
            "final_score": 0.92,
            "metadata": {"node_id": "n2-1", "section_path": "第二章/2.1 系统架构"}
        },
        {
            "content": "项目背景介绍",
            "final_score": 0.85,
            "metadata": {"node_id": "n1-1", "section_path": "第一章/1.1 项目背景"}
        }
    ]

    scope = await nav_search.identify_scope(
        db_session, mock_kb_with_tree, "系统架构", candidates
    )

    assert scope is not None
    assert scope["node_id"] == "n2-1"
    assert scope["confidence"] > 0.5
```

### Step 4.3: 提交代码

- [ ] **提交导航式检索**

```bash
git add backend/app/core/retrieval/navigation.py backend/tests/test_navigation.py
git commit -m "feat(core): add navigation-based retrieval"
```

---

## Task 5: 检索服务整合

**优先级:** P0
**预计时间:** 2小时

### Step 5.1: 实现检索服务

- [ ] **整合所有检索组件**

Create: `backend/app/services/retrieval_service.py`

```python
"""检索服务：整合向量检索、关键词检索、重排序、导航式检索。"""
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.retrieval.hybrid_search import VectorSearch, KeywordSearch
from app.core.retrieval.rrf import rrf_fusion
from app.core.retrieval.reranker import Reranker
from app.core.retrieval.navigation import NavigationSearch
from app.core.retrieval.embedder import Embedder
from app.schemas.retrieval import RetrievalRequest, RetrievalResult, RetrievalCandidate
import time

class RetrievalService:
    """检索服务。"""

    async def retrieve(
        self,
        session: AsyncSession,
        request: RetrievalRequest
    ) -> RetrievalResult:
        """执行检索。

        完整流程：向量化 → 向量检索 → 关键词检索 → RRF融合 → 重排序 → 导航过滤

        Args:
            session: 数据库会话
            request: 检索请求

        Returns:
            检索结果
        """
        start_time = time.time()

        # 1. 向量化查询
        embedder = Embedder(request.kb_id)  # 使用知识库配置的模型
        query_vector = await embedder.embed_query(request.query)

        candidates = []

        # 2. 混合检索
        if request.method in ["hybrid", "vector"]:
            vector_searcher = VectorSearch(embedder)
            vector_results = await vector_searcher.search(
                session,
                request.kb_id,
                query_vector,
                top_k=request.vector_top_k,
                filters=request.metadata_filters
            )
        else:
            vector_results = []

        if request.method in ["hybrid", "keyword"]:
            keyword_searcher = KeywordSearch()
            keyword_results = await keyword_searcher.search(
                session,
                request.kb_id,
                request.query,
                top_k=request.keyword_top_k,
                filters=request.metadata_filters
            )
        else:
            keyword_results = []

        # 3. RRF 融合
        if request.method == "hybrid":
            candidates = rrf_fusion(vector_results, keyword_results, k=60)
        elif request.method == "vector":
            candidates = vector_results
        else:
            candidates = keyword_results

        # 4. 重排序
        if request.rerank_enabled and len(candidates) > 0:
            reranker = Reranker(request.kb_id)  # 使用知识库配置的模型
            candidates = await reranker.rerank(
                request.query,
                candidates,
                top_n=request.rerank_top_n
            )

        # 5. 导航式检索
        if request.navigation_enabled and len(candidates) > 0:
            nav_search = NavigationSearch()
            scope = await nav_search.identify_scope(
                session,
                request.kb_id,
                request.query,
                candidates[:5]  # 使用Top-5识别范围
            )
            if scope:
                candidates = await nav_search.apply_navigation_filter(
                    session,
                    request.kb_id,
                    candidates,
                    scope
                )

        # 6. 截取 Top-K
        candidates = candidates[:request.top_k]

        # 7. 格式化结果
        elapsed_ms = int((time.time() - start_time) * 1000)

        return RetrievalResult(
            query=request.query,
            candidates=[
                RetrievalCandidate(
                    rank=c["rank"],
                    chunk_id=c["chunk_id"],
                    document_id=c["document_id"],
                    document_name=c["document_name"],
                    content=c["content"],
                    page_number=c["page_number"],
                    vector_score=c.get("vector_score", 0),
                    keyword_score=c.get("keyword_score", 0),
                    final_score=c.get("rrf_score", c.get("rerank_score", 0)),
                    metadata=c.get("metadata", {})
                )
                for c in candidates
            ],
            total=len(candidates),
            retrieval_time_ms=elapsed_ms
        )
```

### Step 5.2: 实现检索 API

- [ ] **创建检索接口**

Create: `backend/app/api/v2/retrieval.py`

```python
"""检索接口。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.user import User
from app.schemas.retrieval import RetrievalRequest, RetrievalResult
from app.services.retrieval_service import RetrievalService

router = APIRouter(tags=["retrieval"])

@router.post("/retrieval")
async def retrieve(
    request: RetrievalRequest,
    me: User = Depends(get_current_user)
):
    """执行检索。

    支持向量检索、关键词检索、混合检索，可配置重排序和导航式检索。
    """
    async with async_session() as session:
        service = RetrievalService()
        result = await service.retrieve(session, request)

    return ok(result.model_dump())
```

### Step 5.3: 提交代码

- [ ] **提交检索服务和接口**

```bash
git add backend/app/services/retrieval_service.py backend/app/api/v2/retrieval.py
git commit -m "feat(api): add retrieval service and endpoint"
```

---

## Task 6: 检索测试服务

**优先级:** P1
**预计时间:** 3小时

**说明:** 检索测试功能用于自动化评估检索质量，计算 Hit@K、Recall@K 等指标。

### Step 6.1: 实现测试运行 ORM

- [ ] **创建测试运行和结果模型**

Create: `backend/app/models/retrieval_test_run.py`

```python
"""检索测试运行 ORM。"""
from sqlalchemy import Column, String, JSON, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
import uuid

class RetrievalTestRun(Base):
    """测试运行。"""
    __tablename__ = "retrieval_test_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_set_id = Column(UUID(as_uuid=True), ForeignKey("retrieval_test_sets.id"), nullable=False)
    kb_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False)
    status = Column(String(20), default="pending")  # pending/running/completed/canceled/failed
    config_snapshot = Column(JSON, default=dict)  # 配置快照
    total_cases = Column(Integer, default=0)
    completed_cases = Column(Integer, default=0)
    metrics = Column(JSON, default=dict)  # {hit_at_k: {}, recall_at_k: {}}
    error = Column(String(500))
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default="now())
```

### Step 6.2: 实现测试服务

- [ ] **创建检索测试服务**

Create: `backend/app/services/retrieval_test_service.py`

```python
"""检索测试服务。"""
from typing import Dict, List, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.retrieval_test_set import RetrievalTestSet
from app.models.retrieval_test_case import RetrievalTestCase
from app.models.retrieval_test_run import RetrievalTestRun
from app.schemas.retrieval import RetrievalRequest
from app.services.retrieval_service import RetrievalService

class RetrievalTestService:
    """检索测试服务。"""

    async def run_test(
        self,
        session: AsyncSession,
        run_id: str
    ):
        """执行检索测试。

        Args:
            session: 数据库会话
            run_id: 测试运行ID
        """
        # 1. 加载测试运行
        run = await session.scalar(
            select(RetrievalTestRun).where(RetrievalTestRun.id == run_id)
        )

        if not run or run.status != "pending":
            return

        # 2. 加载测试用例
        cases = await session.scalars(
            select(RetrievalTestCase)
            .where(RetrievalTestCase.test_set_id == run.test_set_id)
            .where(RetrievalTestCase.enabled == True)
            .order_by(RetrievalTestCase.sort_order)
        )

        # 3. 执行测试
        run.status = "running"
        run.started_at = datetime.utcnow()
        await session.commit()

        results = []
        for case in cases:
            result = await self._test_single_case(session, run, case)
            results.append(result)
            run.completed_cases += 1
            await session.commit()

        # 4. 计算指标
        metrics = self._calculate_metrics(results, run.config_snapshot.get("ks", [3, 5]))
        run.metrics = metrics
        run.status = "completed"
        run.finished_at = datetime.utcnow()
        await session.commit()

    async def _test_single_case(
        self,
        session: AsyncSession,
        run: RetrievalTestRun,
        case: RetrievalTestCase
    ) -> Dict:
        """测试单个用例。"""
        # 执行检索
        request = RetrievalRequest(
            query=case.query,
            kb_id=str(run.kb_id),
            top_k=max(run.config_snapshot.get("ks", [3, 5])),
            **run.config_snapshot.get("override_config", {})
        )

        service = RetrievalService()
        result = await service.retrieve(session, request)

        # 计算命中
        hit_doc_ids = []
        for candidate in result.candidates:
            if candidate.document_id in case.expected_doc_ids:
                hit_doc_ids.append(candidate.document_id)

        return {
            "case_id": str(case.id),
            "query": case.query,
            "expected_doc_ids": case.expected_doc_ids,
            "hit_doc_ids": hit_doc_ids,
            "candidates": [c.model_dump() for c in result.candidates]
        }

    def _calculate_metrics(
        self,
        results: List[Dict],
        ks: List[int]
    ) -> Dict[str, Any]:
        """计算检索指标。"""
        metrics = {
            "hit_at_k": {},
            "recall_at_k": {}
        }

        for k in ks:
            hits = 0
            recalls = []

            for result in results:
                hit_doc_ids = result["hit_doc_ids"][:k]
                expected = result["expected_doc_ids"]

                # Hit@K: 是否命中至少一个期望文档
                if len(hit_doc_ids) > 0:
                    hits += 1

                # Recall@K: 命中的期望文档比例
                if len(expected) > 0:
                    recall = len(set(hit_doc_ids) & set(expected)) / len(expected)
                    recalls.append(recall)

            metrics["hit_at_k"][str(k)] = hits / len(results) if results else 0
            metrics["recall_at_k"][str(k)] = sum(recalls) / len(recalls) if recalls else 0

        return metrics
```

### Step 6.3: 创建 ARQ 任务

- [ ] **创建后台任务**

Create: `backend/app/worker/retrieval_test_worker.py`

```python
"""检索测试 ARQ 任务。"""
from arq import cron
from app.db.session import async_session
from app.services.retrieval_test_service import RetrievalTestService

async def run_retrieval_test(ctx, run_id: str):
    """执行检索测试任务。"""
    async with async_session() as session:
        service = RetrievalTestService()
        await service.run_test(session, run_id)

class WorkerSettings:
    """ARQ Worker 设置。"""
    functions = [run_retrieval_test]
    cron_jobs = []
```

### Step 6.4: 提交代码

- [ ] **提交检索测试服务**

```bash
git add backend/app/models/retrieval_test*.py backend/app/services/retrieval_test_service.py backend/app/worker/retrieval_test_worker.py
git commit -m "feat(services): add retrieval test execution service"
```

---

## Task 7: 集成测试

**优先级:** P0
**预计时间:** 2小时

### Step 7.1: 端到端测试

- [ ] **测试完整检索流程**

Create: `backend/tests/test_retrieval_e2e.py`

```python
"""检索端到端测试。"""
import pytest
from httpx import AsyncClient
from app.schemas.retrieval import RetrievalRequest

@pytest.mark.asyncio
async def test_full_retrieval_flow(async_client: AsyncClient, auth_headers: dict, kb_with_documents):
    """测试完整检索流程。"""
    # 1. 执行检索
    response = await async_client.post(
        "/api/v2/retrieval",
        json={
            "query": "系统架构设计",
            "kb_id": kb_with_documents,
            "top_k": 5,
            "method": "hybrid",
            "rerank_enabled": True
        },
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0

    result = data["data"]
    assert "candidates" in result
    assert len(result["candidates"]) > 0
    assert result["candidates"][0]["rank"] == 1

    # 2. 创建测试集
    test_set_resp = await async_client.post(
        f"/api/v2/knowledge/{kb_with_documents}/retrieval-test-sets",
        json={"name": "架构设计测试"},
        headers=auth_headers
    )
    test_set_id = test_set_resp.json()["data"]["id"]

    # 3. 添加测试用例
    await async_client.post(
        f"/api/v2/retrieval-test-sets/{test_set_id}/cases",
        json={
            "query": "系统架构",
            "expected_doc_ids": [result["candidates"][0]["document_id"]],
            "enabled": True
        },
        headers=auth_headers
    )

    # 4. 运行测试
    run_resp = await async_client.post(
        f"/api/v2/retrieval-test-sets/{test_set_id}/runs",
        json={"ks": [3, 5]},
        headers=auth_headers
    )

    assert run_resp.status_code == 200
```

### Step 7.2: 性能测试

- [ ] **测试检索性能**

Create: `backend/tests/test_retrieval_performance.py`

```python
"""检索性能测试。"""
import pytest
import time

@pytest.mark.asyncio
async def test_retrieval_performance(async_client: AsyncClient, auth_headers: dict, kb_with_many_chunks):
    """测试检索响应时间。"""
    start = time.time()

    response = await async_client.post(
        "/api/v2/retrieval",
        json={
            "query": "测试查询",
            "kb_id": kb_with_many_chunks,
            "top_k": 10,
            "method": "hybrid"
        },
        headers=auth_headers
    )

    elapsed = time.time() - start

    assert response.status_code == 200
    # 检索应该在1秒内完成
    assert elapsed < 1.0, f"检索耗时 {elapsed}秒，超过1秒阈值"
```

### Step 7.3: 提交测试

- [ ] **提交集成测试**

```bash
git add backend/tests/test_retrieval_*.py
git commit -m "test: add retrieval e2e and performance tests"
```

---

## 验收标准

- [ ] 混合检索（向量+关键词）正常工作
- [ ] RRF 融合算法正确实现
- [ ] Reranker 重排序功能可用
- [ ] 导航式检索能智能识别范围
- [ ] 检索测试可运行并计算指标
- [ ] 所有测试通过
- [ ] 检索响应时间 < 1秒（1000 chunks）

---

## 风险和依赖

**风险:**
1. pgvector 性能：需要合适的索引（IVFFlat）
2. Embedding 模型延迟：可能影响检索速度
3. Reranker 调用延迟：可能增加响应时间

**依赖:**
- pgvector 扩展已安装
- pg_trgm 扩展已安装
- Embedding 模型已配置
- Reranker 模型已配置

---

**计划保存至:** `docs/superpowers/plans/2026-09-08-phase2-retrieval.md`