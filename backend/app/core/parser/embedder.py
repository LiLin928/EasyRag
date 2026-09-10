# backend/app/core/parser/embedder.py
"""文档向量化器"""

import logging
from typing import List, Optional
import asyncio

from langchain_core.embeddings import Embeddings
from sqlalchemy import update

from app.db.session import async_session
from app.models.chunk import Chunk
from app.providers.langchain_factory import build_embeddings, build_embeddings_from_config
from app.services.kb_config_helper import get_kb_with_model_config

logger = logging.getLogger(__name__)


class Embedder:
    """文档向量化器

    职责：
    - 批量向量化 chunks
    - 调用已配置的 Embedding 模型
    - 存储向量到数据库
    - 错误重试
    """

    def __init__(self, batch_size: int = 20, max_retries: int = 3):
        """
        初始化向量化器

        Args:
            batch_size: 批处理大小
            max_retries: 最大重试次数
        """
        self.batch_size = batch_size
        self.max_retries = max_retries

    async def embed(
        self,
        chunks: List[dict],
        kb_id: str
    ) -> int:
        """
        向量化 chunks

        Args:
            chunks: 分块列表，每项包含 id, content, document_id, kb_id
            kb_id: 知识库 ID

        Returns:
            int: 成功向量化的数量
        """
        logger.info(f"Embedding chunks: kb_id={kb_id}, count={len(chunks)}")

        if not chunks:
            return 0

        # 1. 获取 Embedding 模型
        embeddings = await self._get_embeddings_model(kb_id)
        model_name = getattr(embeddings, 'model', 'unknown')

        # 2. 提取文本内容
        texts = [chunk["content"] for chunk in chunks]

        # 3. 批量向量化（带重试）
        for attempt in range(self.max_retries + 1):
            try:
                vectors = await self._embed_batch(embeddings, texts, self.batch_size)
                break
            except Exception as exc:
                if attempt == self.max_retries:
                    logger.error(f"Embedding failed after {self.max_retries + 1} attempts: {exc}")
                    raise
                logger.warning(f"Embedding attempt {attempt + 1} failed, retrying: {exc}")
                await asyncio.sleep(2 ** attempt)  # 指数退避

        # 4. 更新数据库
        await self._update_embeddings(chunks, vectors, model_name)

        logger.info(f"Embedding completed: success={len(chunks)}/{len(chunks)}")
        return len(chunks)

    async def _get_embeddings_model(self, kb_id: str) -> Embeddings:
        """
        获取 Embeddings 模型

        Args:
            kb_id: 知识库 ID

        Returns:
            LangChain Embeddings 实例
        """
        # 尝试从知识库配置获取
        kb, model_config = await get_kb_with_model_config(kb_id)

        if model_config:
            # 使用知识库指定的模型
            logger.info(f"Using KB-specific embedding model: {model_config.name}")
            return await build_embeddings_from_config(model_config)
        else:
            # 使用默认模型
            logger.info(f"Using default embedding model for KB {kb_id}")
            return await build_embeddings()

    @staticmethod
    async def _embed_batch(
        embeddings: Embeddings,
        texts: List[str],
        batch_size: int = 20
    ) -> List[List[float]]:
        """
        批量向量化文本

        Args:
            embeddings: LangChain Embeddings 实例
            texts: 文本列表
            batch_size: 批处理大小

        Returns:
            向量列表
        """
        all_vectors = []

        # 分批处理，避免 API 限制
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            vectors = await embeddings.aembed_documents(batch)
            all_vectors.extend(vectors)
            logger.debug(f"Embedded batch {i//batch_size + 1}: {len(batch)} texts")

        return all_vectors

    @staticmethod
    async def _update_embeddings(
        chunks: List[dict],
        vectors: List[List[float]],
        model_name: str
    ) -> None:
        """
        更新向量到数据库

        Args:
            chunks: 分块列表
            vectors: 向量列表
            model_name: 模型名称
        """
        import uuid

        async with async_session() as session:
            for chunk, vector in zip(chunks, vectors):
                chunk_uuid = uuid.UUID(chunk["id"])
                await session.execute(
                    update(Chunk)
                    .where(Chunk.id == chunk_uuid)
                    .values(
                        embedding=vector,
                        embedding_model=model_name
                    )
                )

            await session.commit()
            logger.info(f"Updated {len(chunks)} chunks with embeddings")