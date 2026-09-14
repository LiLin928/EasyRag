"""混合检索引擎。

实现向量检索和关键词检索功能。
"""
from typing import List, Dict, Any, Optional
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from app.models.chunk import Chunk, EMBEDDING_DIM
from app.core.retrieval.embedder import Embedder
from app.core.retrieval.metadata_filter import MetadataFilterBuilder


class VectorSearch:
    """向量检索器。

    使用 pgvector 进行向量相似度检索。
    """

    def __init__(self, embedder: Embedder):
        """初始化向量检索器。

        Args:
            embedder: Embedding 封装实例
        """
        self.embedder = embedder

    async def search(
        self,
        session: AsyncSession,
        kb_id: str,
        query_vector: List[float],
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """执行向量检索。

        使用 CTE 先过滤元数据，再进行向量相似度检索。

        Args:
            session: 数据库会话
            kb_id: 知识库ID
            query_vector: 查询向量
            top_k: 返回数量
            filters: 元数据过滤条件（DSL格式）

        Returns:
            检索结果列表
        """
        # 验证向量维度
        if len(query_vector) != EMBEDDING_DIM:
            raise ValueError(f"向量维度不匹配：期望 {EMBEDDING_DIM}，实际 {len(query_vector)}")

        # 构建元数据过滤条件
        filter_builder = MetadataFilterBuilder()
        where_clause, params = filter_builder.build_where_clause(filters, table_alias="c")

        # 构建 CTE 查询
        # 第一阶段：通过元数据过滤缩小范围
        # 第二阶段：在过滤后的数据上计算向量相似度
        cte_query = f"""
        WITH filtered_chunks AS (
            SELECT
                id,
                document_id,
                content,
                page_number,
                metadata,
                embedding
            FROM chunks c
            WHERE c.kb_id = :kb_id
                AND c.enabled = true
                AND c.embedding IS NOT NULL
                AND {where_clause}
        )
        SELECT
            id as chunk_id,
            document_id,
            content,
            page_number,
            metadata,
            1 - (embedding <=> :query_vector) as vector_score
        FROM filtered_chunks
        ORDER BY embedding <=> :query_vector
        LIMIT :top_k
        """

        # 准备查询参数
        query_params = {
            "kb_id": kb_id,
            "query_vector": f"[{','.join(str(x) for x in query_vector)}]",  # 向量格式化为 [1.0, 2.0, ...]
            "top_k": top_k,
            **params  # 合并元数据过滤参数
        }

        # 执行原生SQL查询
        result = await session.execute(text(cte_query), query_params)
        rows = result.fetchall()

        # 格式化结果
        candidates = []
        for idx, row in enumerate(rows):
            candidates.append({
                "rank": idx + 1,
                "vector_rank": idx + 1,  # 向量检索排名
                "chunk_id": str(row.chunk_id),
                "document_id": str(row.document_id),
                "document_name": "",  # 需要关联查询
                "content": row.content,
                "page_number": row.page_number,
                "vector_score": float(row.vector_score) if row.vector_score is not None else 0.0,
                "keyword_score": 0.0,
                "fulltext_rank": None,  # 向量检索时没有关键词排名
                "metadata": row.metadata or {}
            })

        return candidates


class KeywordSearch:
    """关键词检索器。

    使用 pg_trgm 进行全文检索。
    """

    async def search(
        self,
        session: AsyncSession,
        kb_id: str,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """执行关键词检索。

        使用 CTE 先过滤元数据，再进行关键词匹配。
        使用 pg_trgm 三元组相似度进行模糊匹配。

        Args:
            session: 数据库会话
            kb_id: 知识库ID
            query: 查询文本
            top_k: 返回数量
            filters: 元数据过滤条件（DSL格式）

        Returns:
            检索结果列表
        """
        # 构建元数据过滤条件
        filter_builder = MetadataFilterBuilder()
        where_clause, params = filter_builder.build_where_clause(filters, table_alias="c")

        # 降低相似度阈值以支持短查询
        await session.execute(text('SET pg_trgm.similarity_threshold = 0.01'))

        # 构建 CTE 查询
        # 第一阶段：通过元数据过滤缩小范围
        # 第二阶段：在过滤后的数据上进行关键词匹配
        cte_query = f"""
        WITH filtered_chunks AS (
            SELECT
                id,
                document_id,
                content,
                content_search,
                page_number,
                metadata
            FROM chunks c
            WHERE c.kb_id = :kb_id
                AND c.enabled = true
                AND c.content_search IS NOT NULL
                AND {where_clause}
        )
        SELECT
            id as chunk_id,
            document_id,
            content,
            page_number,
            metadata,
            similarity(content_search, :query) as keyword_score
        FROM filtered_chunks
        ORDER BY keyword_score DESC
        LIMIT :top_k
        """

        # 准备查询参数
        query_params = {
            "kb_id": kb_id,
            "query": query,
            "top_k": top_k,
            **params  # 合并元数据过滤参数
        }

        # 执行原生SQL查询
        result = await session.execute(text(cte_query), query_params)
        rows = result.fetchall()

        # 格式化结果
        candidates = []
        for idx, row in enumerate(rows):
            candidates.append({
                "rank": idx + 1,
                "vector_rank": None,  # 关键词检索时没有向量排名
                "fulltext_rank": idx + 1,  # 关键词检索排名
                "chunk_id": str(row.chunk_id),
                "document_id": str(row.document_id),
                "document_name": "",  # 需要关联查询
                "content": row.content,
                "page_number": row.page_number,
                "vector_score": 0.0,
                "keyword_score": float(row.keyword_score) if row.keyword_score is not None else 0.0,
                "metadata": row.metadata or {}
            })

        return candidates