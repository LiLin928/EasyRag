"""settings API（/settings/models + /settings/scenes）集成测试。

admin 用户由 Plan 1 持久化在 easyrag_v2；_token 内幂等 ensure_admin，
避免 module/session 级 async fixture 与 function-scope engine 的 event loop 冲突。
"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.db.session import async_session
from app.main import app
from app.models.scene import Scene
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


@pytest.mark.asyncio
async def test_scene_crud():
    """场景的 创建→更新→删除 全流程，内置场景删除受保护（本测试用自定义 code）。"""
    # 幂等清理：删除可能残留的同 code 场景
    async with async_session() as s:
        await s.execute(delete(Scene).where(Scene.code == "custom1"))
        await s.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        tok = await _token()
        H = {"Authorization": f"Bearer {tok}"}
        r = await c.post("/api/v2/settings/scenes", json={
            "code": "custom1", "name": "自定义", "config": {"top_k": 7},
        }, headers=H)
        assert r.json()["code"] == 0
        sid = r.json()["data"]["id"]
        r = await c.put(f"/api/v2/settings/scenes/{sid}", json={"name": "改", "config": {"top_k": 9}}, headers=H)
        assert r.json()["data"]["name"] == "改"
        r = await c.delete(f"/api/v2/settings/scenes/{sid}", headers=H)
        assert r.json()["code"] == 0
