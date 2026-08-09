"""parse-tasks API（解析进度轮询）集成测试。"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.db.session import async_session
from app.main import app
from app.models.document import Document, ParseTask
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
async def test_get_parse_task():
    """查询解析任务应返回其 status/pct；专用 KB 级联清理保证幂等。"""
    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(KnowledgeBase.name == "ParseTaskApi_KB"))
        await s.commit()
        u = (await s.execute(select(User))).scalars().first()
        kb = KnowledgeBase(user_id=u.id, name="ParseTaskApi_KB", scene="general")
        s.add(kb)
        await s.flush()
        d = Document(kb_id=kb.id, user_id=u.id, name="t.md", ext="md", size=1, file_key="k/t.md")
        s.add(d)
        await s.flush()
        t = ParseTask(doc_id=d.id, kb_id=str(kb.id), status="parsing", pct=50)
        s.add(t)
        await s.commit()
        tid = str(t.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(f"/api/v2/parse-tasks/{tid}", headers={"Authorization": f"Bearer {await _token()}"})
    body = r.json()["data"]
    assert body["status"] == "parsing" and body["pct"] == 50
