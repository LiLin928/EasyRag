"""Embedding 模型封装。

提供统一的 Embedding 接口，支持从模型配置ID构建 Embeddings 实例。
"""
from typing import List, Optional
from langchain_core.embeddings import Embeddings
from app.providers.langchain_factory import build_embeddings


class Embedder:
    """Embedding 模型封装类。

    封装 LangChain Embeddings，提供统一的向量化接口。
    支持延迟加载和实例缓存。

    Attributes:
        model_id: 模型配置ID
        _embeddings: LangChain Embeddings 实例（延迟加载）
    """

    def __init__(self, model_id: str):
        """初始化 Embedder。

        Args:
            model_id: 模型配置ID（对应 settings 表中的模型配置）
        """
        self.model_id = model_id
        self._embeddings: Optional[Embeddings] = None

    async def get_embeddings(self) -> Embeddings:
        """获取 Embeddings 实例。

        延迟加载 Embeddings 实例，首次调用时从模型配置构建。

        Returns:
            LangChain Embeddings 实例

        Raises:
            Exception: 模型配置不存在或构建失败
        """
        if self._embeddings is None:
            self._embeddings = await build_embeddings(self.model_id)
        return self._embeddings

    async def embed_query(self, text: str) -> List[float]:
        """向量化单个查询。

        将查询文本转换为向量表示。

        Args:
            text: 查询文本

        Returns:
            向量（list of float）

        Raises:
            Exception: 向量化失败
        """
        embeddings = await self.get_embeddings()
        return await embeddings.aembed_query(text)

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量向量化文档。

        将多个文档文本转换为向量表示。

        Args:
            texts: 文本列表

        Returns:
            向量列表（每个元素是一个向量）

        Raises:
            Exception: 向量化失败
        """
        embeddings = await self.get_embeddings()
        return await embeddings.aembed_documents(texts)

    def clear_cache(self) -> None:
        """清除缓存的 Embeddings 实例。

        用于在模型配置更新后重新加载。
        """
        self._embeddings = None