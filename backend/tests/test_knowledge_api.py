"""knowledge API（/knowledge CRUD）集成测试。"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.db.session import async_session
from app.main import app
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.security.init_admin import ensure_admin
from app.security.jwt import create_access_token


async def _token() -> str:
    """确保 admin 存在（幂等）并签发其 access token。"""
    await ensure_admin()
    async with async_session() as s:
        u = (await s.execute(select(User))).scalars().first()
    return create_access_token(u.id)


@pytest.mark.asyncio
async def test_kb_crud():
    """知识库 创建→列表→更新→删除 全流程；专用名 + 清理保证可重复运行。"""
    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(KnowledgeBase.name.like("KBApiTest%")))
        await s.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        tok = await _token()
        H = {"Authorization": f"Bearer {tok}"}
        r = await c.post("/api/v2/knowledge", json={"name": "KBApiTest", "scene": "general"}, headers=H)
        assert r.json()["code"] == 0
        kb_id = r.json()["data"]["id"]
        r = await c.get("/api/v2/knowledge", headers=H)
        assert any(k["id"] == kb_id for k in r.json()["data"])
        r = await c.put(f"/api/v2/knowledge/{kb_id}", json={"name": "KBApiTest改"}, headers=H)
        assert r.json()["data"]["name"] == "KBApiTest改"
        r = await c.delete(f"/api/v2/knowledge/{kb_id}", headers=H)
        assert r.json()["code"] == 0
