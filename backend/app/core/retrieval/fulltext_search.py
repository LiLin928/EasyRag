"""全文检索（pg_trgm 相似度）。"""
from sqlalchemy import text

from app.db.session import async_session

_SQL = """
SELECT id, document_id, content, clause_title, section_path, page_number,
       similarity(content_search, :q) AS score
FROM chunks
WHERE kb_id = ANY(:kb_ids)
  AND (cast(:doc_ids as uuid[]) IS NULL OR document_id = ANY(cast(:doc_ids as uuid[])))
  AND (cast(:scope as uuid[]) IS NULL OR id = ANY(cast(:scope as uuid[])))
  AND content_search % :q
ORDER BY score DESC
LIMIT :k
"""


async def search(query: str, kb_ids: list[str], doc_ids: list[str] | None,
                 scope: list[str] | None, top_k: int) -> list[dict]:
    """全文检索：pg_trgm 相似度，返回带 score 的 chunks（按相似度降序）。

    Args:
        query: 查询文本。
        kb_ids: 限定的知识库 id 列表。
        doc_ids: 限定的文档 id 列表（None 表示不限）。
        scope: 缩域 chunk id 列表（None 表示不限）。
        top_k: 返回条数上限。

    Returns:
        命中 chunk 字典列表（含 score）。
    """
    async with async_session() as s:
        rows = (await s.execute(text(_SQL), {
            "q": query, "kb_ids": kb_ids, "doc_ids": doc_ids, "scope": scope, "k": top_k,
        })).mappings().all()
    return [dict(r) for r in rows]
