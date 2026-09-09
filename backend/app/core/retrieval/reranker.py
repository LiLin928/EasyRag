"""重排序器模块。

提供 Reranker 封装和条件重排序功能。
"""
from typing import List, Dict, Any, Optional
from app.providers.rerank.api_reranker import ApiReranker
from app.providers.langchain_factory import build_reranker_from_config
from app.models.model_config import ModelConfig
from app.db.session import async_session
from sqlalchemy import select


class Reranker:
    """重排序器封装类。

    封装 Reranker Provider，提供统一的重排序接口。
    支持延迟加载和实例缓存。

    Attributes:
        model_id: 模型配置ID
        _reranker: Reranker 实例（延迟加载）
    """

    def __init__(self, model_id: str):
        """初始化 Reranker。

        Args:
            model_id: 模型配置ID（对应 settings 表中的模型配置）
        """
        self.model_id = model_id
        self._reranker: Optional[ApiReranker] = None

    async def get_reranker(self) -> ApiReranker:
        """获取 Reranker 实例。

        延迟加载 Reranker 实例，首次调用时从模型配置构建。

        Returns:
            Reranker 实例

        Raises:
            Exception: 模型配置不存在或构建失败
        """
        if self._reranker is None:
            # 从数据库加载模型配置
            async with async_session() as session:
                cfg = await session.scalar(
                    select(ModelConfig).where(ModelConfig.id == self.model_id)
                )
                if not cfg:
                    raise ValueError(f"模型配置不存在: {self.model_id}")

                self._reranker = await build_reranker_from_config(cfg)

        return self._reranker

    async def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_n: int = 10
    ) -> List[Dict[str, Any]]:
        """重排序候选结果。

        Args:
            query: 查询文本
            candidates: 候选结果列表
            top_n: 返回数量

        Returns:
            重排序后的结果列表
        """
        if not candidates:
            return []

        reranker = await self.get_reranker()

        # 构造文档列表
        documents = [c["content"] for c in candidates]

        # 执行重排序
        ranked_indices = await reranker.rerank(query, documents, top_n)

        # 格式化结果
        reranked = []
        for idx, score in ranked_indices:
            original = candidates[idx]
            reranked.append({
                **original,
                "rank": len(reranked) + 1,
                "rerank_score": score,
                "final_score": score
            })

        return reranked

    def clear_cache(self) -> None:
        """清除缓存的 Reranker 实例。

        用于在模型配置更新后重新加载。
        """
        self._reranker = None


def should_rerank(fused: list[dict], threshold: float) -> bool:
    """判断是否需要 rerank：头部两条 RRF 分数差小于阈值时触发。

    Args:
        fused: RRF 融合后的结果（按 rrf 降序）。
        threshold: 触发阈值（差值小于此值表示头部不确定，需 rerank）。

    Returns:
        是否触发 rerank。
    """
    if len(fused) < 2:
        return False
    return (fused[0]["rrf_score"] - fused[1]["rrf_score"]) < threshold


async def conditional_rerank(query: str, fused: list[dict], top_n: int, reranker) -> list[dict]:
    """调用 reranker 精排，按 rerank_score 返回。

    Args:
        query: 查询文本。
        fused: 待 rerank 的融合结果。
        top_n: 返回条数。
        reranker: RerankProvider 实例（rerank 方法返回 [(原索引, 分数)]）。

    Returns:
        rerank 后的字典列表（含 rerank_score）。
    """
    docs = [f["content"] for f in fused]
    ranked = await reranker.rerank(query, docs, top_n)  # [(orig_idx, score)]
    return [{**fused[i], "rerank_score": sc} for i, sc in ranked]
