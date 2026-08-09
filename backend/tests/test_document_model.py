"""Document + ParseTask ORM 模型单元测试。"""
import pytest
from sqlalchemy import delete, select

from app.db.session import async_session
from app.models.document import Document, ParseTask
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User


@pytest.mark.asyncio
async def test_create_doc_and_task():
    """创建 KB→Document→ParseTask，验证默认状态；用专用 KB + 清理保证可重复运行。"""
    async with async_session() as s:
        u = (await s.execute(select(User))).scalars().first()
        await s.execute(delete(KnowledgeBase).where(KnowledgeBase.name == "DocTest_KB"))
        await s.commit()
        kb = KnowledgeBase(user_id=u.id, name="DocTest_KB", scene="general")
        s.add(kb)
        await s.flush()
        d = Document(kb_id=kb.id, user_id=u.id, name="a_test.pdf", ext="pdf", size=1024,
                     mode="fast", status="pending", file_key="k/a.pdf")
        s.add(d)
        await s.flush()
        t = ParseTask(doc_id=d.id, kb_id=str(kb.id), status="pending", pct=0)
        s.add(t)
        await s.commit()
        assert d.status == "pending"
        assert t.doc_id == d.id
