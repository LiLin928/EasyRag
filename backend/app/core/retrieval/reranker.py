"""条件 Rerank：当 RRF 头部得分接近时触发 Reranker 精排。"""


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
    return (fused[0]["rrf"] - fused[1]["rrf"]) < threshold


async def rerank(query: str, fused: list[dict], top_n: int, reranker) -> list[dict]:
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
