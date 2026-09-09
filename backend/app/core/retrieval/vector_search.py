"""Vector retrieval using pgvector cosine distance."""
from sqlalchemy import text

from app.core.retrieval.metadata_filter import (
    MetadataFilter,
    build_predicates_for_kbs,
)
from app.db.session import async_session


_SQL = """
SELECT c.id, c.document_id, d.name AS document_name,
       c.content, c.clause_title, c.section_path, c.page_number,
       c.metadata AS metadata, c.char_count, c.embedding_model,
       1 - (c.embedding <=> cast(:emb as vector)) AS vector_score
FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.kb_id::text = ANY(cast(:kb_ids as text[]))
  AND d.enabled
  AND c.enabled
  AND (cast(:doc_ids as uuid[]) IS NULL OR c.document_id = ANY(cast(:doc_ids as uuid[])))
  AND (cast(:scope as uuid[]) IS NULL OR c.id = ANY(cast(:scope as uuid[])))
  AND (cast(:embedding_model as text) IS NULL OR c.embedding_model = cast(:embedding_model as text))
  AND (cast(:similarity_threshold as double precision) IS NULL
       OR 1 - (c.embedding <=> cast(:emb as vector)) >= cast(:similarity_threshold as double precision))
  AND c.embedding IS NOT NULL
"""

_ORDER = """
ORDER BY c.embedding <=> cast(:emb as vector), c.id
LIMIT :k
"""


def _hit(row) -> dict:
    return {
        "id": str(row["id"]),
        "document_id": str(row["document_id"]),
        "document_name": row["document_name"],
        "content": row["content"],
        "clause_title": row["clause_title"],
        "section_path": row["section_path"],
        "page_number": row["page_number"],
        "metadata": row["metadata"] or {},
        "char_count": row["char_count"],
        "embedding_model": row["embedding_model"],
        "vector_score": float(row["vector_score"]),
        "keyword_score": None,
    }


async def search(
    q_emb: list[float],
    kb_ids: list[str],
    doc_ids: list[str] | None,
    scope: list[str] | None,
    top_k: int,
    metadata_filter: MetadataFilter | None = None,
    embedding_model: str | None = None,
    similarity_threshold: float | None = None,
) -> list[dict]:
    """Return enabled cosine-similar chunks with metadata predicates applied."""
    async with async_session() as s:
        predicates, predicate_params = await build_predicates_for_kbs(
            s, kb_ids, metadata_filter
        )
        sql = _SQL
        if predicates:
            sql += " AND " + " AND ".join(predicates)
        sql += _ORDER
        rows = (
            await s.execute(
                text(sql),
                {
                    "emb": str(q_emb),
                    "kb_ids": kb_ids,
                    "doc_ids": doc_ids,
                    "scope": scope,
                    "k": top_k,
                    "embedding_model": embedding_model,
                    "similarity_threshold": similarity_threshold,
                    **predicate_params,
                },
            )
        ).mappings().all()
    return [_hit(row) for row in rows]
