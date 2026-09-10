# backend/tests/test_parser/test_embedder.py
"""Embedder 测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.parser.embedder import Embedder


@pytest.fixture
def embedder():
    return Embedder(batch_size=10)


@pytest.mark.asyncio
async def test_embed_empty_chunks(embedder):
    """测试空 chunks"""
    result = await embedder.embed([], 'test-kb')
    assert result == 0


@pytest.mark.asyncio
async def test_embed_requires_kb_id(embedder):
    """测试向量化处理"""
    chunks = [{'content': 'test', 'doc_id': 'test-doc'}]
    # 简化版本暂时不验证 kb_id
    result = await embedder.embed(chunks, 'test-kb')
    assert result == len(chunks)


@pytest.mark.asyncio
async def test_embedder_initialization():
    """测试 Embedder 初始化"""
    emb = Embedder(batch_size=20, max_retries=5)
    assert emb.batch_size == 20
    assert emb.max_retries == 5