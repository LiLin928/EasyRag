"""RRF (Reciprocal Rank Fusion) 融合算法。

RRF 是一种简单有效的多路检索结果融合方法。
"""
from typing import List, Dict


def rrf_fusion(
    vector_results: List[Dict],
    keyword_results: List[Dict],
    k: int = 60
) -> List[Dict]:
    """RRF 融合向量检索和关键词检索结果。

    RRF公式: score(d) = sum(1 / (k + rank(d)))

    Args:
        vector_results: 向量检索结果
        keyword_results: 关键词检索结果
        k: RRF 参数（默认60，经验值）

    Returns:
        融合后的结果列表（按 RRF 分数降序排列）
    """
    # 构建文档ID到结果的映射
    doc_scores: Dict[str, Dict] = {}

    # 累加向量检索分数
    for result in vector_results:
        doc_id = result["chunk_id"]
        rank = result["rank"]
        rrf_score = 1 / (k + rank)

        if doc_id not in doc_scores:
            doc_scores[doc_id] = {
                **result,
                "vector_score": result["vector_score"],
                "keyword_score": 0.0,
                "vector_rank": result.get("vector_rank"),  # 保留向量排名
                "fulltext_rank": None,  # 向量检索时没有关键词排名
                "rrf_score": 0.0
            }
        doc_scores[doc_id]["rrf_score"] += rrf_score

    # 累加关键词检索分数
    for result in keyword_results:
        doc_id = result["chunk_id"]
        rank = result["rank"]
        rrf_score = 1 / (k + rank)

        if doc_id not in doc_scores:
            doc_scores[doc_id] = {
                **result,
                "vector_score": 0.0,
                "keyword_score": result["keyword_score"],
                "vector_rank": None,  # 关键词检索时没有向量排名
                "fulltext_rank": result.get("fulltext_rank"),  # 保留关键词排名
                "rrf_score": 0.0
            }
        doc_scores[doc_id]["rrf_score"] += rrf_score
        doc_scores[doc_id]["keyword_score"] = result["keyword_score"]
        # 如果同一个文档在向量检索中也存在，更新 fulltext_rank
        if result.get("fulltext_rank") is not None:
            doc_scores[doc_id]["fulltext_rank"] = result["fulltext_rank"]

    # 按 RRF 分数排序
    sorted_results = sorted(
        doc_scores.values(),
        key=lambda x: x["rrf_score"],
        reverse=True
    )

    # 重新分配排名，并计算最终分数
    for idx, result in enumerate(sorted_results):
        result["rank"] = idx + 1
        result["final_score"] = result["rrf_score"]

    return sorted_results


def weighted_fusion(
    vector_results: List[Dict],
    keyword_results: List[Dict],
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3
) -> List[Dict]:
    """加权融合向量检索和关键词检索结果。

    简单的线性加权融合方法。

    Args:
        vector_results: 向量检索结果
        keyword_results: 关键词检索结果
        vector_weight: 向量检索权重
        keyword_weight: 关键词检索权重

    Returns:
        融合后的结果列表（按加权分数降序排列）
    """
    # 归一化分数
    def normalize_scores(results: List[Dict], score_key: str) -> List[Dict]:
        if not results:
            return results

        scores = [r[score_key] for r in results]
        max_score = max(scores) if scores else 1.0
        min_score = min(scores) if scores else 0.0
        score_range = max_score - min_score if max_score != min_score else 1.0

        for r in results:
            r["normalized_score"] = (r[score_key] - min_score) / score_range

        return results

    # 归一化
    vector_results = normalize_scores(vector_results.copy(), "vector_score")
    keyword_results = normalize_scores(keyword_results.copy(), "keyword_score")

    # 构建文档ID到结果的映射
    doc_scores: Dict[str, Dict] = {}

    # 累加向量检索分数
    for result in vector_results:
        doc_id = result["chunk_id"]
        if doc_id not in doc_scores:
            doc_scores[doc_id] = {
                **result,
                "vector_score": result["vector_score"],
                "keyword_score": 0.0,
                "vector_rank": result.get("vector_rank"),  # 保留向量排名
                "fulltext_rank": None,  # 向量检索时没有关键词排名
                "weighted_score": 0.0
            }
        doc_scores[doc_id]["weighted_score"] += result.get("normalized_score", 0) * vector_weight

    # 累加关键词检索分数
    for result in keyword_results:
        doc_id = result["chunk_id"]
        if doc_id not in doc_scores:
            doc_scores[doc_id] = {
                **result,
                "vector_score": 0.0,
                "keyword_score": result["keyword_score"],
                "vector_rank": None,  # 关键词检索时没有向量排名
                "fulltext_rank": result.get("fulltext_rank"),  # 保留关键词排名
                "weighted_score": 0.0
            }
        doc_scores[doc_id]["weighted_score"] += result.get("normalized_score", 0) * keyword_weight
        doc_scores[doc_id]["keyword_score"] = result["keyword_score"]
        # 如果同一个文档在向量检索中也存在，更新 fulltext_rank
        if result.get("fulltext_rank") is not None:
            doc_scores[doc_id]["fulltext_rank"] = result["fulltext_rank"]

    # 按加权分数排序
    sorted_results = sorted(
        doc_scores.values(),
        key=lambda x: x["weighted_score"],
        reverse=True
    )

    # 重新分配排名，并计算最终分数
    for idx, result in enumerate(sorted_results):
        result["rank"] = idx + 1
        result["final_score"] = result["weighted_score"]

    return sorted_results