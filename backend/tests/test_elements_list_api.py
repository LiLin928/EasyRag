"""elements API（文档元素列表）集成测试。"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.db.session import async_session
from app.main import app
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.tree_node import ElementPosition
from app.models.user import User
from app.security.init_admin import ensure_admin
from app.security.jwt import create_access_token


@pytest.mark.asyncio
async def test_list_elements():
    """列出文档元素，返回 element_id/type；专用 KB 级联清理保证幂等。"""
    await ensure_admin()
    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(KnowledgeBase.name == "ElementsApi_KB"))
        await s.commit()
        u = (await s.execute(select(User))).scalars().first()
        kb = KnowledgeBase(user_id=u.id, name="ElementsApi_KB", scene="general")
        s.add(kb)
        await s.flush()
        d = Document(kb_id=kb.id, user_id=u.id, name="t.pdf", ext="pdf", size=1, file_key="k/t.pdf")
        s.add(d)
        await s.flush()
        s.add(ElementPosition(document_id=d.id, element_type="text", element_index=0,
                              page_number=1, content="A"))
        s.add(ElementPosition(document_id=d.id, element_type="table", element_index=1,
                              page_number=1, content="<table/>"))
        await s.commit()
        doc_id = str(d.id)
        tok = create_access_token(u.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(f"/api/v2/documents/{doc_id}/elements",
                        headers={"Authorization": f"Bearer {tok}"})
    data = r.json()["data"]
    assert data["total"] >= 2
    assert all("element_id" in e and "type" in e for e in data["list"])
