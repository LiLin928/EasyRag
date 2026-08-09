"""Chunk ORM 模型单元测试。"""
import pytest
from sqlalchemy import delete, select

from app.db.session import async_session
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User


@pytest.mark.asyncio
async def test_create_chunk_without_embedding():
    """创建分块，验证 embedding 默认为 None（未向量化前）；专用 KB + 清理保证可重复运行。"""
    async with async_session() as s:
        u = (await s.execute(select(User))).scalars().first()
        await s.execute(delete(KnowledgeBase).where(KnowledgeBase.name == "ChunkTest_KB"))
        await s.commit()
        kb = KnowledgeBase(user_id=u.id, name="ChunkTest_KB", scene="general")
        s.add(kb)
        await s.flush()
        d = Document(kb_id=kb.id, user_id=u.id, name="c.pdf", ext="pdf", size=1, file_key="k/c.pdf")
        s.add(d)
        await s.flush()
        c = Chunk(document_id=d.id, kb_id=str(kb.id), content="hello",
                  content_search="hello", page_number=1, seq=0)
        s.add(c)
        await s.commit()
        assert c.id is not None
        assert c.embedding is None
