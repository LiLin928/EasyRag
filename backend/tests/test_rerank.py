"""Rerank provider（ApiReranker）单元测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.providers.rerank.api_reranker import ApiReranker


@pytest.mark.asyncio
async def test_rerank_maps_scores():
    """rerank 应调用 rerank HTTP API，并按 relevance_score 降序返回 (原索引, 分数) 列表。

    httpx 的 Response.json() / raise_for_status() 均为同步方法，故响应桩用 MagicMock
    （而非 AsyncMock），与真实 httpx 行为一致。
    """
    r = ApiReranker(url="http://x", api_key="k", model="bge-reranker")
    fake = MagicMock()
    fake.json.return_value = {"results": [
        {"index": 1, "relevance_score": 0.9},
        {"index": 0, "relevance_score": 0.5},
    ]}
    fake.raise_for_status.return_value = None
    with patch("app.providers.rerank.api_reranker.httpx.AsyncClient.post", AsyncMock(return_value=fake)):
        ranked = await r.rerank("q", ["a", "b"], top_n=2)
    assert ranked == [(1, 0.9), (0, 0.5)]
