"""TreeBuilder（结构树构建）单元测试。"""
import pytest
from sqlalchemy import delete, select

from app.core.parser.models import ParsedElement
from app.core.parser.tree_builder import build_tree
from app.db.session import async_session
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User


@pytest.mark.asyncio
async def test_build_hierarchy():
    """构建层级树：同级标题平级，子标题 parent 指向上一级；专用 KB 级联清理保证幂等。"""
    async with async_session() as s:
        u = (await s.execute(select(User))).scalars().first()
        await s.execute(delete(KnowledgeBase).where(KnowledgeBase.name == "TreeBuild_KB"))
        await s.commit()
        kb = KnowledgeBase(user_id=u.id, name="TreeBuild_KB", scene="general")
        s.add(kb)
        await s.flush()
        d = Document(kb_id=kb.id, user_id=u.id, name="t.pdf", ext="pdf", size=1, file_key="k/t.pdf")
        s.add(d)
        await s.commit()
        doc_id = str(d.id)
    elems = [
        ParsedElement("heading", "第一章", 1, level=1),
        ParsedElement("text", "x", 1),
        ParsedElement("heading", "1.1 概述", 2, level=2),
        ParsedElement("heading", "第二章", 3, level=1),
    ]
    nodes = await build_tree(doc_id, elems)
    levels = [n.level for n in nodes]
    assert 1 in levels and 2 in levels
    ones = [n for n in nodes if n.level == 1]
    assert len(ones) == 2
    child = [n for n in nodes if n.title == "1.1 概述"][0]
    assert child.parent_id == ones[0].id
