"""场景接口测试。"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client():
    """创建异步测试客户端。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_list_scenes_unauthorized(client: AsyncClient):
    """测试未认证访问场景列表。"""
    response = await client.get("/api/v2/scenes")
    # 业务异常返回 HTTP 200 + 错误码
    assert response.status_code == 200
    data = response.json()
    # 错误码应该在 40100-40199 范围（认证错误）
    assert data["code"] >= 40100 and data["code"] < 40200
    assert "message" in data