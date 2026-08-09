"""HybridRetriever（LangChain BaseRetriever）单元测试。"""
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.documents import Document

from app.core.retrieval.hybrid_retriever import HybridRetriever


@pytest.mark.asyncio
async def test_retriever_returns_documents():
    """ainvoke 应返回 LangChain Document，metadata 含 chunk_id。"""
    r = HybridRetriever(doc_ids=["d1"], scene_config=AsyncMock(navigation_enabled=False))
    with patch.object(r._pipeline, "search", AsyncMock(return_value=type("R", (), {
        "chunks": [{"id": "c1", "content": "hi", "document_id": "d1", "clause_title": "t", "page_number": 1}],
        "references": [], "nav_info": None, "mode": "hybrid", "rerank_triggered": False
    })())):
        docs = await r.ainvoke("q")
    assert len(docs) == 1 and isinstance(docs[0], Document)
    assert docs[0].metadata["chunk_id"] == "c1"
