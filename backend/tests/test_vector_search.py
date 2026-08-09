"""vector_search（pgvector 余弦）单元测试。"""
import pytest
from sqlalchemy import text

from app.core.retrieval.vector_search import search
from app.db.session import async_session
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase


@pytest.mark.asyncio
async def test_vector_search_returns_scored():
    """插入带向量的 chunk，向量检索应命中并返回 score/content。

    修正 plan：document_id 用真实 Document（满足 FK），kb_id 用专用字符串，
    清理专用 KB（级联删 doc/chunk）保证可重复运行且不破坏其它数据。
    """
    async with async_session() as s:
        await s.execute(text("DELETE FROM knowledge_bases WHERE name = 'VecSearch_KB'"))
        await s.commit()
        u = (await s.execute(text("SELECT id FROM users LIMIT 1"))).scalar()
        kb = KnowledgeBase(user_id=u, name="VecSearch_KB", scene="general")
        s.add(kb)
        await s.flush()
        d = Document(kb_id=kb.id, user_id=u, name="v.pdf", ext="pdf", size=1, file_key="k/v.pdf")
        s.add(d)
        await s.flush()
        doc_id = str(d.id)
        emb = str([0.1] * 1024)
        await s.execute(text(
            "INSERT INTO chunks (id, document_id, kb_id, content, content_search, page_number, seq, element_count, embedding) "
            "VALUES (gen_random_uuid(), :doc, 'vec_kb_test', '叉车参数', '叉车参数', 1, 0, 0, cast(:emb as vector))"
        ), {"doc": doc_id, "emb": emb})
        await s.commit()
    hits = await search(q_emb=[0.1] * 1024, kb_ids=["vec_kb_test"], doc_ids=None, scope=None, top_k=5)
    assert len(hits) == 1
    assert "score" in hits[0] and "content" in hits[0]
