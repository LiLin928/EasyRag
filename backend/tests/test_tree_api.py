"""tree API（文档结构树）集成测试。"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.parser.models import ParsedElement
from app.core.parser.tree_builder import build_tree
from app.db.session import async_session
from app.main import app
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.security.init_admin import ensure_admin
from app.security.jwt import create_access_token


@pytest.mark.asyncio
async def test_tree_nested_shape():
    """结构树应返回嵌套形状；专用 KB 级联清理保证幂等。"""
    await ensure_admin()
    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(KnowledgeBase.name == "TreeApi_KB"))
        await s.commit()
        u = (await s.execute(select(User))).scalars().first()
        kb = KnowledgeBase(user_id=u.id, name="TreeApi_KB", scene="general")
        s.add(kb)
        await s.flush()
        d = Document(kb_id=kb.id, user_id=u.id, name="t.pdf", ext="pdf", size=1, file_key="k/t.pdf")
        s.add(d)
        await s.commit()
        doc_id = str(d.id)
        tok = create_access_token(u.id)
    await build_tree(doc_id, [
        ParsedElement("heading", "第一章", 1, level=1),
        ParsedElement("heading", "1.1 子", 1, level=2),
    ])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(f"/api/v2/documents/{doc_id}/tree", headers={"Authorization": f"Bearer {tok}"})
    tree = r.json()["data"]["tree"]
    assert len(tree) == 1 and tree[0]["title"] == "第一章"
    assert len(tree[0]["children"]) == 1 and tree[0]["children"][0]["title"] == "1.1 子"
