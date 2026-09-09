"""检索服务。

整合 Embedder、混合检索、RRF 融合、Reranker、导航式检索到统一服务。
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
import time

from app.core.retrieval.embedder import Embedder
from app.core.retrieval.hybrid_search import VectorSearch, KeywordSearch
from app.core.retrieval.rrf import rrf_fusion
from app.core.retrieval.reranker import Reranker, should_rerank, conditional_rerank
from app.core.retrieval.navigation import NavigationSearch
from app.schemas.retrieval import RetrievalRequest, RetrievalResult, RetrievalCandidate


class RetrievalService:
    """检索服务。

    提供完整的检索流程：向量化 → 混合检索 → RRF融合 → 重排序 → 导航过滤。
    """

    async def retrieve(
        self,
        session: AsyncSession,
        request: RetrievalRequest,
        embedder: Optional[Embedder] = None,
        reranker: Optional[Reranker] = None
    ) -> RetrievalResult:
        """执行检索。

        完整流程：向量化 → 向量检索 → 关键词检索 → RRF融合 → 重排序 → 导航过滤。

        Args:
            session: 数据库会话
            request: 检索请求
            embedder: Embedder 实例（可选，用于向量化）
            reranker: Reranker 实例（可选，用于重排序）

        Returns:
            检索结果
        """
        start_time = time.time()

        # 1. 向量化查询（如果需要向量检索）
        query_vector = None
        if request.method in ["hybrid", "vector"] and embedder:
            query_vector = await embedder.embed_query(request.query)

        candidates = []

        # 2. 混合检索
        if request.method in ["hybrid", "vector"] and query_vector:
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
        if request.rerank_enabled and len(candidates) > 0 and reranker:
            # 检查是否需要重排序
            if should_rerank(candidates, threshold=0.05):
                # 只对前 N 个进行重排序
                top_n = min(request.rerank_top_n, len(candidates))
                candidates = await reranker.rerank(
                    request.query,
                    candidates[:top_n],
                    top_n=top_n
                )

        # 5. 导航式检索
        if request.navigation_enabled and len(candidates) > 0:
            nav_search = NavigationSearch()
            scope = await nav_search.identify_scope(
                session,
                request.kb_id,
                request.query,
                candidates[:5],  # 使用 Top-5 识别范围
                embedder
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
                    document_name=c.get("document_name", ""),
                    content=c["content"],
                    page_number=c["page_number"],
                    vector_score=c.get("vector_score", 0),
                    keyword_score=c.get("keyword_score", 0),
                    final_score=c.get("final_score", 0),
                    metadata=c.get("metadata", {})
                )
                for c in candidates
            ],
            total=len(candidates),
            retrieval_time_ms=elapsed_ms
        )