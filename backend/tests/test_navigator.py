"""navigator（结构导航缩域）单元测试。"""
from unittest.mock import AsyncMock, patch

import pytest

from app.core.retrieval.navigator import navigate


@pytest.mark.asyncio
async def test_navigate_returns_anchors():
    """头部置信度 margin >= threshold 时缩域，返回 anchors 与 scope_chunk_ids。"""
    with patch("app.core.retrieval.navigator._fetch_nodes", AsyncMock(return_value=[
        {"id": "n1", "document_id": "d1", "title": "4.2 验收", "page_start": 28, "page_end": 30, "level": 2, "score": 0.91},
        {"id": "n2", "document_id": "d1", "title": "4.3 交付", "page_start": 31, "page_end": 33, "level": 2, "score": 0.50},
    ])), patch("app.core.retrieval.navigator._chunks_in_pages", AsyncMock(return_value=["c1", "c2"])):
        r = await navigate(q_emb=[0.1] * 8, doc_ids=["d1"], top_k=2, threshold=0.15)
    assert r["scoped"] is True              # 0.91-0.50=0.41 >= 0.15
    assert r["scope_chunk_ids"] == ["c1", "c2"]
    assert r["anchors"][0]["title"] == "4.2 验收"
