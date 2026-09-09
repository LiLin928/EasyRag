"""混合检索引擎。

实现向量检索和关键词检索功能。
"""
from typing import List, Dict, Any, Optional
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from app.models.chunk import Chunk, EMBEDDING_DIM
from app.core.retrieval.embedder import Embedder


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

        Args:
            session: 数据库会话
            kb_id: 知识库ID
            query_vector: 查询向量
            top_k: 返回数量
            filters: 元数据过滤条件

        Returns:
            检索结果列表
        """
        # 验证向量维度
        if len(query_vector) != EMBEDDING_DIM:
            raise ValueError(f"向量维度不匹配：期望 {EMBEDDING_DIM}，实际 {len(query_vector)}")

        # 构建查询
        q = select(Chunk).where(
            and_(
                Chunk.kb_id == kb_id,
                Chunk.enabled == True,
                Chunk.embedding.isnot(None)
            )
        )

        # 元数据过滤
        if filters:
            for key, value in filters.items():
                q = q.where(Chunk.metadata_[key].astext == str(value))

        # 向量相似度计算（余弦距离）
        # pgvector 的 cosine_distance 返回距离，需要转换为相似度
        q = q.order_by(
            Chunk.embedding.cosine_distance(query_vector)
        ).limit(top_k)

        # 执行查询
        results = await session.execute(q)
        chunks = results.scalars().all()

        # 格式化结果
        candidates = []
        for idx, chunk in enumerate(chunks):
            # 计算相似度分数（距离转相似度）
            # 余弦距离 = 1 - 余弦相似度，所以相似度 = 1 - 距离
            distance_query = select(
                Chunk.embedding.cosine_distance(query_vector)
            ).where(Chunk.id == chunk.id)
            distance = await session.scalar(distance_query)

            similarity = 1 - distance if distance is not None else 0

            candidates.append({
                "rank": idx + 1,
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "document_name": "",  # 需要关联查询
                "content": chunk.content,
                "page_number": chunk.page_number,
                "vector_score": float(similarity),
                "keyword_score": 0.0,
                "metadata": chunk.metadata_ or {}
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

        使用 pg_trgm 三元组相似度进行模糊匹配。

        Args:
            session: 数据库会话
            kb_id: 知识库ID
            query: 查询文本
            top_k: 返回数量
            filters: 元数据过滤条件

        Returns:
            检索结果列表
        """
        # 构建查询
        q = select(Chunk).where(
            and_(
                Chunk.kb_id == kb_id,
                Chunk.enabled == True,
                Chunk.content_search.isnot(None)
            )
        )

        # 元数据过滤
        if filters:
            for key, value in filters.items():
                q = q.where(Chunk.metadata_[key].astext == str(value))

        # 全文搜索：在 content_search 中查找
        # 使用 pg_trgm 相似度或包含查询
        q = q.where(
            Chunk.content_search.op('%')(query)  # 包含查询词
        ).order_by(
            func.similarity(Chunk.content_search, query).desc()
        ).limit(top_k)

        results = await session.execute(q)
        chunks = results.scalars().all()

        candidates = []
        for idx, chunk in enumerate(chunks):
            # 计算关键词相似度
            similarity = await session.scalar(
                func.similarity(Chunk.content_search, query)
            )

            candidates.append({
                "rank": idx + 1,
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "document_name": "",  # 需要关联查询
                "content": chunk.content,
                "page_number": chunk.page_number,
                "vector_score": 0.0,
                "keyword_score": float(similarity or 0),
                "metadata": chunk.metadata_ or {}
            })

        return candidates