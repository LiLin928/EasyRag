"""TreeNode + ElementPosition ORM 模型单元测试。"""
import pytest
from sqlalchemy import delete, select

from app.db.session import async_session
from app.models.tree_node import TreeNode, ElementPosition
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User


@pytest.mark.asyncio
async def test_create_tree_and_element():
    """创建 TreeNode 与 ElementPosition，验证关联；专用 KB + 清理保证可重复运行。"""
    async with async_session() as s:
        u = (await s.execute(select(User))).scalars().first()
        await s.execute(delete(KnowledgeBase).where(KnowledgeBase.name == "TreeTest_KB"))
        await s.commit()
        kb = KnowledgeBase(user_id=u.id, name="TreeTest_KB", scene="general")
        s.add(kb)
        await s.flush()
        d = Document(kb_id=kb.id, user_id=u.id, name="t.pdf", ext="pdf", size=1, file_key="k/t.pdf")
        s.add(d)
        await s.flush()
        n = TreeNode(document_id=d.id, level=0, sort_order=0, title="第一章", page_start=1, page_end=5)
        s.add(n)
        await s.flush()
        e = ElementPosition(document_id=d.id, tree_node_id=n.id, element_type="text",
                            element_index=0, page_number=1, content="正文")
        s.add(e)
        await s.commit()
        assert n.id and e.id
