"""Rerank provider 抽象基类。

LangChain 1.X 无标准 Rerank 抽象，故 EasyRAG 自研统一接口，
供检索管线（Plan 4）以同一契约调用不同 rerank 服务。
"""
from abc import ABC, abstractmethod


class RerankProvider(ABC):
    """Rerank 服务统一抽象。"""

    @abstractmethod
    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        """对 documents 相对 query 重排序，返回得分最高的若干条。

        Args:
            query: 查询文本。
            documents: 候选文档原文列表。
            top_n: 返回的条数上限。

        Returns:
            [(原文档索引, relevance_score), ...]，按分数降序。
        """
