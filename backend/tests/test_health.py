import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health_ok():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/health")
        body = r.json()
        assert r.status_code == 200
        assert body["code"] == 0
        assert body["data"]["db"] == "ok"
