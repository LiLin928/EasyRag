"""结构导航：用 nav_embedding 定位章节，按页码范围缩域检索。"""
from sqlalchemy import text

from app.db.session import async_session

_NODE_SQL = """
SELECT id, document_id, title, page_start, page_end, level,
       1 - (nav_embedding <=> cast(:emb as vector)) AS score
FROM doc_tree_nodes
WHERE document_id = ANY(cast(:doc_ids as uuid[])) AND level > 0 AND nav_embedding IS NOT NULL
ORDER BY nav_embedding <=> cast(:emb as vector) LIMIT :k
"""


async def _fetch_nodes(q_emb, doc_ids, top_k):
    """查 nav_embedding 最相关的章节节点。"""
    async with async_session() as s:
        rows = (await s.execute(text(_NODE_SQL), {
            "emb": str(q_emb), "doc_ids": doc_ids, "k": top_k,
        })).mappings().all()
    return [dict(r) for r in rows]


async def _chunks_in_pages(ranges: list[tuple]) -> list[str]:
    """ranges: [(doc_id, page_start, page_end), ...] → 收集这些页码范围内的 chunk id。"""
    ids: list[str] = []
    async with async_session() as s:
        for doc_id, ps, pe in ranges:
            rows = (await s.execute(text(
                "SELECT id::text FROM chunks WHERE document_id = :d AND page_number BETWEEN :ps AND :pe"),
                {"d": doc_id, "ps": ps or 1, "pe": pe or 9999})).mappings().all()
            ids.extend(r["id"] for r in rows)
    return ids


async def navigate(q_emb: list[float], doc_ids: list[str], top_k: int, threshold: float) -> dict:
    """导航：用 nav_embedding 找最相关章节；若头部置信度 margin >= threshold 则按页码缩域。

    Returns:
        {scoped, anchors, scope_chunk_ids, confidence}
    """
    nodes = await _fetch_nodes(q_emb, doc_ids, top_k)
    if not nodes:
        return {"scoped": False, "anchors": [], "scope_chunk_ids": None, "confidence": 0.0}
    top = nodes[0]
    second = nodes[1] if len(nodes) > 1 else None
    confidence = float(top["score"])
    margin = confidence - (float(second["score"]) if second else 1.0)
    scoped = margin >= threshold
    scope = None
    if scoped:
        ranges = [(str(n["document_id"]), n["page_start"], n["page_end"]) for n in nodes[:top_k]]
        scope = await _chunks_in_pages(ranges)
    anchors = [{"node_id": str(n["id"]), "title": n["title"], "confidence": float(n["score"])}
               for n in nodes[:top_k]]
    return {"scoped": scoped, "anchors": anchors, "scope_chunk_ids": scope, "confidence": confidence}
