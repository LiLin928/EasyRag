"""documents API（上传/列表/详情/删除）集成测试。"""
import io
from unittest.mock import AsyncMock, patch

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
async def test_upload_returns_task_and_doc(monkeypatch, tmp_path):
    """上传 md 文档应返回 task_id/doc_id 并入队解析任务（mock create_pool 避免 redis 依赖）。"""
    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(KnowledgeBase.name == "DocUpload_KB"))
        await s.commit()
        u = (await s.execute(select(User))).scalars().first()
        kb = KnowledgeBase(user_id=u.id, name="DocUpload_KB", scene="general")
        s.add(kb)
        await s.commit()
        kb_id = str(kb.id)
    monkeypatch.setattr("app.config.settings.storage_local_dir", str(tmp_path))
    fake_pool = AsyncMock()
    fake_pool.enqueue_job = AsyncMock()
    with patch("app.api.v2.documents.create_pool", AsyncMock(return_value=fake_pool)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            tok = await _token()
            r = await c.post("/api/v2/documents/upload",
                             headers={"Authorization": f"Bearer {tok}"},
                             files={"file": ("t.md", io.BytesIO("# h\n正文".encode("utf-8")), "text/markdown")},
                             data={"kbId": kb_id, "mode": "fast"})
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["task_id"] and body["data"]["doc_id"]
    fake_pool.enqueue_job.assert_called_once()
