"""retrieval pipeline（编排）单元测试。"""
from unittest.mock import AsyncMock, patch

import pytest

from app.core.retrieval.pipeline import RetrievalPipeline


@pytest.mark.asyncio
async def test_pipeline_orchestrates():
    """pipeline 编排：embed→向量+全文→RRF→引用；mock 各检索路，验证结果组装。"""
    p = RetrievalPipeline(scene_config=AsyncMock(
        vector_top_k=10, trgm_top_k=10, top_k=5,
        rerank_enabled=False, rerank_threshold=0.02, navigation_enabled=False,
        vector_weight=0.7, keyword_weight=0.3, rrf_k=60, rerank_top_n=5))
    with patch.object(p, "_embed_query", AsyncMock(return_value=[0.1] * 8)), \
         patch("app.core.retrieval.pipeline.vector_search.search",
               AsyncMock(return_value=[{"id": "a", "content": "A"}])), \
         patch("app.core.retrieval.pipeline.fulltext_search.search", AsyncMock(return_value=[])):
        r = await p.search(query="q", doc_ids=["d1"], top_k=5)
    assert len(r.chunks) >= 1
    assert r.references is not None
