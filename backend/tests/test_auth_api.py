import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.security.init_admin import ensure_admin
from app.config import settings


@pytest.fixture(autouse=True)
async def _admin():
    await ensure_admin()   # idempotent; admin already exists from Task 10


@pytest.mark.asyncio
async def test_login_success_and_userinfo():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/v2/auth/login", json={"username": settings.init_admin_username, "password": settings.init_admin_password})
        body = r.json()
        assert r.status_code == 200
        assert body["code"] == 0
        token = body["data"]["access_token"]
        assert body["data"]["refresh_token"]
        assert body["data"]["user"]["username"] == settings.init_admin_username
        r2 = await c.get("/api/v2/auth/user-info", headers={"Authorization": f"Bearer {token}"})
        assert r2.json()["code"] == 0


@pytest.mark.asyncio
async def test_login_wrong_password():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/v2/auth/login", json={"username": settings.init_admin_username, "password": "wrong"})
        assert r.json()["code"] == 40103


@pytest.mark.asyncio
async def test_refresh_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        login = await c.post("/api/v2/auth/login", json={"username": settings.init_admin_username, "password": settings.init_admin_password})
        rt = login.json()["data"]["refresh_token"]
        r = await c.post("/api/v2/auth/refresh", json={"refresh_token": rt})
        assert r.json()["code"] == 0
        assert r.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_userinfo_without_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/v2/auth/user-info")
        assert r.json()["code"] == 40101
