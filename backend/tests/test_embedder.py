"""Embedder 测试。

测试 Embedding 模型封装功能。
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.retrieval.embedder import Embedder


@pytest.fixture
def mock_embeddings():
    """创建模拟的 Embeddings 实例。"""
    embeddings = AsyncMock()
    embeddings.aembed_query = AsyncMock(return_value=[0.1] * 1024)
    embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 1024, [0.2] * 1024])
    return embeddings


@pytest.mark.asyncio
async def test_embedder_initialization():
    """测试 Embedder 初始化。"""
    embedder = Embedder("model-embedding")

    assert embedder.model_id == "model-embedding"
    assert embedder._embeddings is None


@pytest.mark.asyncio
async def test_embedder_get_embeddings(mock_embeddings):
    """测试获取 Embeddings 实例。"""
    with patch('app.core.retrieval.embedder.build_embeddings', new_callable=AsyncMock) as mock_build:
        mock_build.return_value = mock_embeddings

        embedder = Embedder("model-embedding")
        result = await embedder.get_embeddings()

        # 验证调用了构建函数
        mock_build.assert_called_once_with("model-embedding")

        # 验证返回了 Embeddings 实例
        assert result is mock_embeddings

        # 验证实例被缓存
        assert embedder._embeddings is mock_embeddings


@pytest.mark.asyncio
async def test_embedder_get_embeddings_caches_instance(mock_embeddings):
    """测试 Embeddings 实例被缓存。"""
    with patch('app.core.retrieval.embedder.build_embeddings', new_callable=AsyncMock) as mock_build:
        mock_build.return_value = mock_embeddings

        embedder = Embedder("model-embedding")

        # 第一次调用
        result1 = await embedder.get_embeddings()
        # 第二次调用
        result2 = await embedder.get_embeddings()

        # 验证只调用了一次构建函数（缓存生效）
        mock_build.assert_called_once()

        # 验证两次返回的是同一个实例
        assert result1 is result2


@pytest.mark.asyncio
async def test_embedder_embed_query(mock_embeddings):
    """测试向量化单个查询。"""
    with patch('app.core.retrieval.embedder.build_embeddings', new_callable=AsyncMock) as mock_build:
        mock_build.return_value = mock_embeddings

        embedder = Embedder("model-embedding")
        vector = await embedder.embed_query("测试查询")

        # 验证调用了 aembed_query
        mock_embeddings.aembed_query.assert_called_once_with("测试查询")

        # 验证返回了向量
        assert isinstance(vector, list)
        assert len(vector) == 1024
        assert all(isinstance(v, float) for v in vector)


@pytest.mark.asyncio
async def test_embedder_embed_documents(mock_embeddings):
    """测试批量向量化文档。"""
    with patch('app.core.retrieval.embedder.build_embeddings', new_callable=AsyncMock) as mock_build:
        mock_build.return_value = mock_embeddings

        embedder = Embedder("model-embedding")
        texts = ["文档1", "文档2"]
        vectors = await embedder.embed_documents(texts)

        # 验证调用了 aembed_documents
        mock_embeddings.aembed_documents.assert_called_once_with(texts)

        # 验证返回了向量列表
        assert isinstance(vectors, list)
        assert len(vectors) == 2
        assert all(isinstance(v, list) for v in vectors)
        assert all(len(v) == 1024 for v in vectors)


@pytest.mark.asyncio
async def test_embedder_clear_cache(mock_embeddings):
    """测试清除缓存。"""
    with patch('app.core.retrieval.embedder.build_embeddings', new_callable=AsyncMock) as mock_build:
        mock_build.return_value = mock_embeddings

        embedder = Embedder("model-embedding")

        # 加载实例
        await embedder.get_embeddings()
        assert embedder._embeddings is not None

        # 清除缓存
        embedder.clear_cache()
        assert embedder._embeddings is None

        # 再次加载会重新调用构建函数
        await embedder.get_embeddings()
        assert mock_build.call_count == 2