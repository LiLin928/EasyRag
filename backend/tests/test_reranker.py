"""reranker（条件触发 + rerank）单元测试。"""
from unittest.mock import AsyncMock

import pytest

from app.core.retrieval.reranker import rerank, should_rerank


def test_should_rerank_when_scores_close():
    """头部 RRF 分数差 < 阈值时触发 rerank。"""
    fused = [{"id": "a", "rrf": 0.032}, {"id": "b", "rrf": 0.030}]
    assert should_rerank(fused, threshold=0.02) is True     # 0.002 < 0.02


def test_should_not_rerank_when_clear():
    """头部 RRF 分数差 >= 阈值时不触发。"""
    fused = [{"id": "a", "rrf": 0.10}, {"id": "b", "rrf": 0.02}]
    assert should_rerank(fused, threshold=0.02) is False    # 0.08 >= 0.02


@pytest.mark.asyncio
async def test_rerank_reorders():
    """rerank 按 reranker 返回的 (索引, 分数) 重排，b 胜出排首位。"""
    fused = [{"id": "a", "content": "A", "rrf": 0.03}, {"id": "b", "content": "B", "rrf": 0.032}]
    rk = AsyncMock()
    rk.rerank = AsyncMock(return_value=[(1, 0.9), (0, 0.5)])  # b（索引1）胜出
    out = await rerank("q", fused, top_n=2, reranker=rk)
    assert out[0]["id"] == "b"
    assert "rerank_score" in out[0]
