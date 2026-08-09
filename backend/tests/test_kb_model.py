"""KnowledgeBase ORM 模型单元测试。"""
import pytest
from sqlalchemy import delete, select

from app.db.session import async_session
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User


@pytest.mark.asyncio
async def test_create_kb():
    """创建知识库，验证默认 chunk_size/doc_count；用专用名 + 清理保证可重复运行。"""
    async with async_session() as s:
        u = (await s.execute(select(User))).scalars().first()
        await s.execute(delete(KnowledgeBase).where(KnowledgeBase.name == "KB1_test_unit"))
        await s.commit()
        kb = KnowledgeBase(user_id=u.id, name="KB1_test_unit", scene="general")
        s.add(kb)
        await s.commit()
        assert kb.id is not None
        assert kb.chunk_size == 512
        assert kb.doc_count == 0
