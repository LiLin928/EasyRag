"""向量检索（pgvector 余弦）。"""
from sqlalchemy import text

from app.db.session import async_session

_SQL = """
SELECT id, document_id, content, clause_title, section_path, page_number,
       1 - (embedding <=> cast(:emb as vector)) AS score
FROM chunks
WHERE kb_id = ANY(:kb_ids)
  AND (cast(:doc_ids as uuid[]) IS NULL OR document_id = ANY(cast(:doc_ids as uuid[])))
  AND (cast(:scope as uuid[]) IS NULL OR id = ANY(cast(:scope as uuid[])))
  AND embedding IS NOT NULL
ORDER BY embedding <=> cast(:emb as vector)
LIMIT :k
"""


async def search(q_emb: list[float], kb_ids: list[str], doc_ids: list[str] | None,
                 scope: list[str] | None, top_k: int) -> list[dict]:
    """向量检索：返回与 q_emb 余弦最相近的 chunks（带 score），按相似度降序。

    Args:
        q_emb: 查询向量。
        kb_ids: 限定的知识库 id 列表。
        doc_ids: 限定的文档 id 列表（None 表示不限）。
        scope: 缩域 chunk id 列表（None 表示不限）。
        top_k: 返回条数上限。

    Returns:
        命中 chunk 字典列表（含 score）。
    """
    async with async_session() as s:
        rows = (await s.execute(text(_SQL), {
            "emb": str(q_emb), "kb_ids": kb_ids,
            "doc_ids": doc_ids, "scope": scope, "k": top_k,
        })).mappings().all()
    return [dict(r) for r in rows]
