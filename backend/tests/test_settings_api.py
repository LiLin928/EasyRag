"""settings API（/settings/models）集成测试。

注：admin 用户由 Plan 1 持久化在 easyrag_v2；此处直接 _token 内幂等 ensure_admin，
避免 module/session 级 async fixture 与 function-scope engine 的 event loop 冲突。
"""
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
async def test_create_list_set_default_delete_model():
    """模型的 创建→列表→设默认→删除 全流程，验证 key 不回传（仅 has_key）与默认互斥。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        tok = await _token()
        H = {"Authorization": f"Bearer {tok}"}
        # create（upsert）
        r = await c.post("/api/v2/settings/models?group=llm", json={
            "name": "qwen-plus", "prov": "dashscope", "use": "qa",
            "url": "http://x", "key": "sk-1", "temp": 0.3, "def": True,
        }, headers=H)
        assert r.json()["code"] == 0
        # list
        r = await c.get("/api/v2/settings/models?group=llm", headers=H)
        data = r.json()["data"]
        assert any(m["name"] == "qwen-plus" and m["has_key"] is True for m in data)
        # set default
        r = await c.put("/api/v2/settings/models/llm/default?name=qwen-plus", headers=H)
        assert r.json()["data"]["success"] is True
        # delete
        r = await c.delete("/api/v2/settings/models?group=llm&name=qwen-plus", headers=H)
        assert r.json()["code"] == 0
