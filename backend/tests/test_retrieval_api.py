"""retrieval API（/navigate /search）集成测试。"""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.session import async_session
from app.main import app
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
async def test_search_api_shape():
    """/search 返回统一响应；mock embedding 与检索路，带 token（修正 plan 缺 token）。"""
    fake = AsyncMock()
    fake.aembed_query = AsyncMock(return_value=[0.1] * 8)
    with patch("app.api.v2.retrieval.build_embeddings", AsyncMock(return_value=fake)), \
         patch("app.api.v2.retrieval.vector_search.search", AsyncMock(return_value=[])), \
         patch("app.api.v2.retrieval.fulltext_search.search", AsyncMock(return_value=[])):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            tok = await _token()
            r = await c.post("/api/v2/search", json={"question": "q", "document_ids": ["d1"]},
                             headers={"Authorization": f"Bearer {tok}"})
    assert r.json()["code"] == 0
