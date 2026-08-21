"""fulltext_search（pg_trgm 相似度）单元测试。"""
import pytest
from sqlalchemy import text

from app.core.retrieval.fulltext_search import search
from app.db.session import async_session
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase


@pytest.mark.asyncio
async def test_fulltext_search():
    """插入含 content_search 的 chunk，全文检索应命中并返回 score（用 ASCII 保证 trigram 命中）。"""
    async with async_session() as s:
        await s.execute(text("DELETE FROM knowledge_bases WHERE name = 'FT_KB'"))
        await s.commit()
        u = (await s.execute(text("SELECT id FROM users LIMIT 1"))).scalar()
        kb = KnowledgeBase(user_id=u, name="FT_KB", scene="general")
        s.add(kb)
        await s.flush()
        d = Document(kb_id=kb.id, user_id=u, name="f.pdf", ext="pdf", size=1, file_key="k/f.pdf")
        s.add(d)
        await s.flush()
        doc_id = str(d.id)
        kb_id = str(kb.id)
        await s.execute(text(
            "INSERT INTO chunks (id, document_id, kb_id, content, content_search, page_number, seq, element_count) "
            "VALUES (gen_random_uuid(), :doc, :kb, 'forklift technical parameters', "
            "'forklift technical parameters', 1, 0, 0)"
        ), {"doc": doc_id, "kb": kb_id})
        await s.commit()
    hits = await search(query="forklift", kb_ids=[kb_id], doc_ids=None, scope=None, top_k=5)
    assert isinstance(hits, list)
    assert all("keyword_score" in h for h in hits)
    assert len(hits) >= 1  # forklift 子串，trigram 相似度应过阈值
