"""Metadata schema API integration tests."""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.db.session import async_session
from app.main import app
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.security.init_admin import ensure_admin
from app.security.jwt import create_access_token


async def _admin() -> User:
    await ensure_admin()
    async with async_session() as s:
        return (await s.execute(select(User))).scalars().first()


async def _second_user(admin: User) -> User:
    username = "metadata-second-user"
    async with async_session() as s:
        existing = (
            await s.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if existing:
            return existing
        user = User(username=username, hashed_password="not-for-login", is_active=True)
        s.add(user)
        await s.commit()
        return user


@pytest.mark.asyncio
async def test_metadata_field_api_contracts_and_ownership():
    admin = await _admin()
    other = await _second_user(admin)
    async with async_session() as s:
        await s.execute(
            delete(KnowledgeBase).where(KnowledgeBase.name == "PlanMetaApiKB")
        )
        await s.commit()
        kb = KnowledgeBase(user_id=admin.id, name="PlanMetaApiKB", scene="general")
        s.add(kb)
        await s.commit()
        kb_id = str(kb.id)

    admin_token = create_access_token(admin.id)
    other_token = create_access_token(other.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        headers = {"Authorization": f"Bearer {admin_token}"}
        other_headers = {"Authorization": f"Bearer {other_token}"}

        response = await client.get(
            f"/api/v2/knowledge/{kb_id}/metadata-fields", headers=headers
        )
        assert response.json()["code"] == 0
        assert len(response.json()["data"]) == 6

        response = await client.get(
            f"/api/v2/knowledge/{kb_id}/metadata-fields", headers=other_headers
        )
        assert response.json()["code"] == 40300

        payload = {
            "key": "clause_type",
            "name": "条款类型",
            "scope": "chunk",
            "data_type": "select",
            "options": ["义务", "权利"],
            "filterable": True,
            "retrieval_filterable": True,
        }
        response = await client.post(
            f"/api/v2/knowledge/{kb_id}/metadata-fields",
            headers=headers,
            json=payload,
        )
        assert response.status_code == 201
        assert response.json()["code"] == 0
        field_id = response.json()["data"]["id"]
        assert response.json()["data"]["retrieval_filterable"] is True

        response = await client.post(
            f"/api/v2/knowledge/{kb_id}/metadata-fields",
            headers=headers,
            json=payload,
        )
        assert response.json()["code"] == 40001

        response = await client.get(
            f"/api/v2/knowledge/{kb_id}/metadata-fields", headers=headers
        )
        assert response.json()["code"] == 0
        fields = response.json()["data"]
        builtin_id = next(field["id"] for field in fields if field["built_in"])
        response = await client.delete(
            f"/api/v2/knowledge/{kb_id}/metadata-fields/{builtin_id}",
            headers=headers,
        )
        assert response.json()["code"] == 40300

        response = await client.delete(
            f"/api/v2/knowledge/{kb_id}/metadata-fields/{field_id}?force=true",
            headers=headers,
        )
        assert response.json()["data"] == {"success": True, "affected_count": 0}
