import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_response_has_request_id():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/health")
        assert "x-request-id" in {k.lower() for k in r.headers}


@pytest.mark.asyncio
async def test_request_id_echoed_when_provided():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/health", headers={"X-Request-ID": "abc-123"})
        assert r.headers["x-request-id"] == "abc-123"
