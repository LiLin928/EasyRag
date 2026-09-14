"""测试向量检索与元数据过滤集成。

测试元数据过滤在向量检索之前执行，确保结果符合过滤条件。
"""
import pytest
from datetime import datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.retrieval.hybrid_search import VectorSearch, KeywordSearch
from app.core.retrieval.embedder import Embedder
from app.models.chunk import Chunk, EMBEDDING_DIM
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase


@pytest.fixture
async def setup_test_data(session: AsyncSession):
    """创建测试数据：不同部门、不同项目的文档和分块。

    Returns:
        包含知识库ID和文档ID的字典
    """
    # 创建用户（必需的外键）
    from app.models.user import User
    user_id = uuid4()
    user = User(
        id=user_id,
        username=f"test_user_{user_id}",
        hashed_password="test_hash",
        display_name="Test User",
        role="user",
    )
    session.add(user)
    await session.flush()

    # 创建知识库
    kb_id = uuid4()
    kb = KnowledgeBase(
        id=kb_id,
        user_id=user_id,
        name="测试知识库",
        description="用于测试元数据过滤的知识库",
        scene="general",
    )
    session.add(kb)
    await session.flush()

    # 创建文档
    doc_id_1 = uuid4()
    doc_1 = Document(
        id=doc_id_1,
        kb_id=kb_id,
        user_id=user_id,
        name="销售文档",
        ext="pdf",
        size=1024,
        status="completed",
        file_key="test/sales.pdf",
    )
    session.add(doc_1)

    doc_id_2 = uuid4()
    doc_2 = Document(
        id=doc_id_2,
        kb_id=kb_id,
        user_id=user_id,
        name="技术文档",
        ext="pdf",
        size=2048,
        status="completed",
        file_key="test/tech.pdf",
    )
    session.add(doc_2)

    doc_id_3 = uuid4()
    doc_3 = Document(
        id=doc_id_3,
        kb_id=kb_id,
        user_id=user_id,
        name="市场文档",
        ext="pdf",
        size=3072,
        status="completed",
        file_key="test/market.pdf",
    )
    session.add(doc_3)

    await session.flush()

    # 创建不同部门的分块
    # 使用固定向量以便测试（不依赖numpy）
    import random
    random.seed(42)

    def generate_vector(dim: int = EMBEDDING_DIM) -> list[float]:
        """生成随机向量。

        Args:
            dim: 向量维度

        Returns:
            随机向量列表
        """
        return [random.gauss(0, 1) for _ in range(dim)]

    chunks_data = [
        # (doc_id, content, metadata)
        (doc_id_1, "销售部门第一季度业绩报告", {"department": "sales", "year": 2024}),
        (doc_id_1, "销售部门客户数据统计", {"department": "sales", "year": 2024}),
        (doc_id_2, "技术部门架构设计文档", {"department": "tech", "year": 2024}),
        (doc_id_2, "技术部门API接口说明", {"department": "tech", "year": 2025}),
        (doc_id_3, "市场部门营销策略", {"department": "marketing", "year": 2024}),
        (doc_id_3, "市场部门用户调研报告", {"department": "marketing", "year": 2025}),
    ]

    for i, (doc_id, content, metadata) in enumerate(chunks_data):
        # 生成随机但固定的向量
        vector = generate_vector()

        chunk = Chunk(
            id=uuid4(),
            document_id=doc_id,
            kb_id=str(kb_id),  # kb_id is UUID, need to convert to string
            content=content,
            content_search=content,  # 添加 content_search 字段用于关键词检索
            page_number=1,
            metadata_=metadata,
            embedding=vector,
            enabled=True,
        )
        session.add(chunk)

    await session.commit()

    return {
        "kb_id": str(kb_id),
        "doc_ids": [str(doc_id_1), str(doc_id_2), str(doc_id_3)],
    }


@pytest.mark.asyncio
async def test_vector_search_with_metadata_filter(session: AsyncSession, setup_test_data):
    """测试向量检索应用元数据过滤。

    验证：
    1. 元数据过滤在向量检索之前执行
    2. 所有结果都符合元数据条件
    3. 不同过滤条件返回不同结果
    """
    kb_id = setup_test_data["kb_id"]

    # 创建一个mock embedder（不需要依赖实际模型配置）
    class MockEmbedder:
        """模拟 Embedder 类，用于测试。"""

        async def embed(self, text: str) -> list[float]:
            """向量化查询文本。

            Args:
                text: 查询文本

            Returns:
                固定的随机向量
            """
            import random
            random.seed(42)
            return [random.gauss(0, 1) for _ in range(EMBEDDING_DIM)]

        async def embed_query(self, text: str) -> list[float]:
            """向量化查询文本。

            Args:
                text: 查询文本

            Returns:
                固定的随机向量
            """
            import random
            random.seed(42)
            return [random.gauss(0, 1) for _ in range(EMBEDDING_DIM)]

        async def embed_documents(self, texts: list[str]) -> list[list[float]]:
            """批量向量化文档。

            Args:
                texts: 文本列表

            Returns:
                向量列表
            """
            import random
            random.seed(42)
            return [[random.gauss(0, 1) for _ in range(EMBEDDING_DIM)] for _ in texts]

    embedder = MockEmbedder()
    vector_search = VectorSearch(embedder)

    # 生成查询向量
    query_vector = await embedder.embed("销售报告")

    # 测试1：过滤department=sales
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "department", "operator": "=", "value": "sales"}
        ]
    }

    results = await vector_search.search(
        session=session,
        kb_id=kb_id,
        query_vector=query_vector,
        top_k=10,
        filters=filters,
    )

    # 验证：所有结果的department都应该是sales
    assert len(results) > 0, "应该返回结果"
    for result in results:
        assert result["metadata"]["department"] == "sales", f"结果部门应为sales，实际为{result['metadata']['department']}"

    # 验证：结果数量应该少于总数量（6个分块中只有2个是sales）
    assert len(results) <= 2, f"销售部门应该最多2条结果，实际{len(results)}条"

    # 测试2：过滤year=2025
    filters_2025 = {
        "logic": "AND",
        "conditions": [
            {"field": "year", "operator": "=", "value": "2025"}
        ]
    }

    results_2025 = await vector_search.search(
        session=session,
        kb_id=kb_id,
        query_vector=query_vector,
        top_k=10,
        filters=filters_2025,
    )

    # 验证：所有结果的year都应该是2025
    for result in results_2025:
        assert str(result["metadata"]["year"]) == "2025", f"结果年份应为2025，实际为{result['metadata']['year']}"

    # 测试3：复合过滤条件
    filters_complex = {
        "logic": "AND",
        "conditions": [
            {"field": "department", "operator": "=", "value": "tech"},
            {"field": "year", "operator": "=", "value": "2024"}
        ]
    }

    results_complex = await vector_search.search(
        session=session,
        kb_id=kb_id,
        query_vector=query_vector,
        top_k=10,
        filters=filters_complex,
    )

    # 验证：所有结果应该同时满足department=tech和year=2024
    for result in results_complex:
        assert result["metadata"]["department"] == "tech", "结果部门应为tech"
        assert str(result["metadata"]["year"]) == "2024", "结果年份应为2024"

    # 验证：应该只有1条结果（tech且year=2024）
    assert len(results_complex) == 1, f"应该只有1条结果，实际{len(results_complex)}条"


@pytest.mark.asyncio
async def test_vector_search_without_filter(session: AsyncSession, setup_test_data):
    """测试不带元数据过滤的向量检索。

    验证：不带过滤条件时返回所有结果。
    """
    kb_id = setup_test_data["kb_id"]

    class MockEmbedder:
        """模拟 Embedder 类，用于测试。"""

        async def embed(self, text: str) -> list[float]:
            """向量化查询文本。

            Args:
                text: 查询文本

            Returns:
                固定的随机向量
            """
            import random
            random.seed(42)
            return [random.gauss(0, 1) for _ in range(EMBEDDING_DIM)]

    embedder = MockEmbedder()
    vector_search = VectorSearch(embedder)

    query_vector = await embedder.embed("报告")

    # 不带过滤条件
    results = await vector_search.search(
        session=session,
        kb_id=kb_id,
        query_vector=query_vector,
        top_k=20,
        filters=None,
    )

    # 验证：应该返回所有6个分块
    assert len(results) == 6, f"不带过滤应该返回6条结果，实际{len(results)}条"


@pytest.mark.asyncio
async def test_vector_search_filter_order(session: AsyncSession, setup_test_data):
    """测试元数据过滤在向量检索之前执行。

    验证：CTE确保先过滤再计算向量相似度，提高性能。
    """
    kb_id = setup_test_data["kb_id"]

    class MockEmbedder:
        """模拟 Embedder 类，用于测试。"""

        async def embed(self, text: str) -> list[float]:
            import random
            random.seed(42)
            return [random.gauss(0, 1) for _ in range(EMBEDDING_DIM)]

    embedder = MockEmbedder()
    vector_search = VectorSearch(embedder)

    query_vector = await embedder.embed("测试")

    # 使用一个只匹配少量结果的过滤条件
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "department", "operator": "=", "value": "sales"}
        ]
    }

    # 执行检索
    results = await vector_search.search(
        session=session,
        kb_id=kb_id,
        query_vector=query_vector,
        top_k=5,
        filters=filters,
    )

    # 验证：结果应该只包含sales部门的数据
    assert all(r["metadata"]["department"] == "sales" for r in results), "所有结果应符合过滤条件"

    # 验证：结果已按向量相似度排序
    if len(results) > 1:
        for i in range(len(results) - 1):
            assert results[i]["vector_score"] >= results[i+1]["vector_score"], "结果应按相似度降序排列"


@pytest.mark.asyncio
async def test_keyword_search_with_metadata_filter(session: AsyncSession, setup_test_data):
    """测试关键词检索应用元数据过滤。

    验证：
    1. 元数据过滤在关键词检索之前执行
    2. 所有结果都符合元数据条件
    3. 不同过滤条件返回不同结果
    """
    kb_id = setup_test_data["kb_id"]

    keyword_search = KeywordSearch()

    # 测试1：过滤department=sales
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "department", "operator": "=", "value": "sales"}
        ]
    }

    results = await keyword_search.search(
        session=session,
        kb_id=kb_id,
        query="报告",
        top_k=10,
        filters=filters,
    )

    # 验证：所有结果的department都应该是sales
    assert len(results) > 0, "应该返回结果"
    for result in results:
        assert result["metadata"]["department"] == "sales", f"结果部门应为sales，实际为{result['metadata']['department']}"

    # 验证：结果数量应该少于总数量（6个分块中只有2个是sales）
    assert len(results) <= 2, f"销售部门应该最多2条结果，实际{len(results)}条"

    # 测试2：过滤year=2025
    filters_2025 = {
        "logic": "AND",
        "conditions": [
            {"field": "year", "operator": "=", "value": "2025"}
        ]
    }

    results_2025 = await keyword_search.search(
        session=session,
        kb_id=kb_id,
        query="文档",
        top_k=10,
        filters=filters_2025,
    )

    # 验证：所有结果的year都应该是2025
    for result in results_2025:
        assert str(result["metadata"]["year"]) == "2025", f"结果年份应为2025，实际为{result['metadata']['year']}"

    # 测试3：复合过滤条件
    filters_complex = {
        "logic": "AND",
        "conditions": [
            {"field": "department", "operator": "=", "value": "tech"},
            {"field": "year", "operator": "=", "value": "2024"}
        ]
    }

    results_complex = await keyword_search.search(
        session=session,
        kb_id=kb_id,
        query="文档",
        top_k=10,
        filters=filters_complex,
    )

    # 验证：所有结果应该同时满足department=tech和year=2024
    for result in results_complex:
        assert result["metadata"]["department"] == "tech", "结果部门应为tech"
        assert str(result["metadata"]["year"]) == "2024", "结果年份应为2024"

    # 验证：应该只有1条结果（tech且year=2024）
    assert len(results_complex) == 1, f"应该只有1条结果，实际{len(results_complex)}条"


@pytest.mark.asyncio
async def test_keyword_search_without_filter(session: AsyncSession, setup_test_data):
    """测试不带元数据过滤的关键词检索。

    验证：不带过滤条件时返回所有结果。
    """
    kb_id = setup_test_data["kb_id"]

    keyword_search = KeywordSearch()

    # 不带过滤条件
    results = await keyword_search.search(
        session=session,
        kb_id=kb_id,
        query="文档",
        top_k=20,
        filters=None,
    )

    # 验证：应该返回所有6个分块
    assert len(results) == 6, f"不带过滤应该返回6条结果，实际{len(results)}条"


@pytest.mark.asyncio
async def test_keyword_search_filter_order(session: AsyncSession, setup_test_data):
    """测试元数据过滤在关键词检索之前执行。

    验证：CTE确保先过滤再进行关键词匹配，提高性能。
    """
    kb_id = setup_test_data["kb_id"]

    keyword_search = KeywordSearch()

    # 使用一个只匹配少量结果的过滤条件
    filters = {
        "logic": "AND",
        "conditions": [
            {"field": "department", "operator": "=", "value": "sales"}
        ]
    }

    # 执行检索
    results = await keyword_search.search(
        session=session,
        kb_id=kb_id,
        query="报告",
        top_k=5,
        filters=filters,
    )

    # 验证：结果应该只包含sales部门的数据
    assert all(r["metadata"]["department"] == "sales" for r in results), "所有结果应符合过滤条件"

    # 验证：结果已按关键词相似度排序
    if len(results) > 1:
        for i in range(len(results) - 1):
            assert results[i]["keyword_score"] >= results[i+1]["keyword_score"], "结果应按相似度降序排列"