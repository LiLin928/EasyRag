"""RRF（Reciprocal Rank Fusion）融合：合并向量与全文检索结果。"""


def merge(vec_hits: list[dict], kw_hits: list[dict],
          w_vec: float = 0.7, w_kw: float = 0.3, k: int = 60) -> list[dict]:
    """按 RRF 融合两路检索结果，返回按 rrf 分数降序的列表。

    RRF 公式：score(d) = Σ w_i / (k + rank_i(d))。两路都命中的文档分数累加，排名更高。

    Args:
        vec_hits: 向量检索结果（按相关度降序）。
        kw_hits: 全文检索结果（按相关度降序）。
        w_vec: 向量路权重。
        w_kw: 全文路权重。
        k: RRF 平滑常数（典型 60）。

    Returns:
        融合后的字典列表，每个含 rrf 分数与 vector_rank/fulltext_rank。
    """
    scores: dict[str, dict] = {}
    for rank, h in enumerate(vec_hits):
        hid = str(h["id"])
        if hid not in scores:
            scores[hid] = {**h, "id": hid, "rrf": 0.0, "vector_rank": rank + 1}
        scores[hid]["rrf"] += w_vec / (k + rank + 1)
    for rank, h in enumerate(kw_hits):
        hid = str(h["id"])
        if hid not in scores:
            scores[hid] = {**h, "id": hid, "rrf": 0.0, "fulltext_rank": rank + 1}
        scores[hid]["rrf"] += w_kw / (k + rank + 1)
    return sorted(scores.values(), key=lambda x: x["rrf"], reverse=True)
