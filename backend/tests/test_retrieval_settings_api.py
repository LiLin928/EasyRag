"""Retrieval settings API integration tests."""
import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.api.deps import get_current_user
from app.db.session import async_session
from app.main import app
from app.models.knowledge_base import KnowledgeBase
from app.models.model_config import ModelConfig
from app.models.user import User
from app.security.init_admin import ensure_admin
from app.security.jwt import create_access_token


async def _token() -> str:
    await ensure_admin()
    async with async_session() as s:
        user = (await s.execute(select(User))).scalars().first()
    return create_access_token(user.id)


async def _model(name: str, grp: str, dim: int | None = None) -> ModelConfig:
    async with async_session() as s:
        await s.execute(delete(ModelConfig).where(
            ModelConfig.grp == grp,
            ModelConfig.name == name,
        ))
        await s.commit()
        model = ModelConfig(
            grp=grp,
            name=name,
            prov="openai",
            use="retrieval" if grp == "embed" else "rerank",
            url="http://localhost",
            params={} if dim is None else {"dim": dim},
            is_default=False,
            enabled=True,
        )
        s.add(model)
        await s.commit()
        await s.refresh(model)
        return model


@pytest.mark.asyncio
async def test_update_uses_field_presence_not_null_defaults(monkeypatch):
    captured = {}

    async def fake_save(**kwargs):
        captured.update(kwargs)
        return {"values": {}, "resolved": {}, "embedding_model": None,
                "rerank_model": None, "rebuild_required": False}

    monkeypatch.setattr(
        "app.api.v2.retrieval_settings.save_retrieval_settings", fake_save
    )
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            response = await client.put(
                "/api/v2/knowledge/00000000-0000-0000-0000-000000000000/retrieval-settings",
                json={"embedding_model_id": None, "retrieval_config": {"method": "hybrid"}},
            )
        assert response.status_code == 200
        assert response.json()["code"] == 0
        assert captured["embedding_model_id"] is None
        assert captured["rerank_model_id"] is None
        assert captured["retrieval_config"] == {"method": "hybrid"}
        assert captured["update_embedding_model"] is True
        assert captured["update_rerank_model"] is False
        assert captured["update_retrieval_config"] is True
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_retrieval_settings_get_update_clear_and_validation():
    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(
            KnowledgeBase.name == "PlanRetrievalSettingsApiKB"
        ))
        await s.commit()

    embed = await _model("plan_api_embed_1024", "embed", 1024)
    bad_dim = await _model("plan_api_embed_768", "embed", 768)
    rerank = await _model("plan_api_rerank", "rerank")
    llm = await _model("plan_api_llm", "llm")

    async with async_session() as s:
        admin = (await s.execute(select(User))).scalars().first()
        other = User(
            username=f"plan_other_{uuid.uuid4().hex[:8]}",
            hashed_password="not-a-login-secret",
            role="user",
        )
        s.add(other)
        kb = KnowledgeBase(
            user_id=admin.id,
            name="PlanRetrievalSettingsApiKB",
            scene="general",
        )
        s.add(kb)
        await s.commit()
        kb_id, other_id = str(kb.id), other.id

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            token = await _token()
            headers = {"Authorization": f"Bearer {token}"}
            base = f"/api/v2/knowledge/{kb_id}/retrieval-settings"

            response = await client.get(base, headers=headers)
            assert response.status_code == 200
            assert response.json()["code"] == 0
            assert response.json()["data"]["values"]["method"]["source"] == "system_default"

            response = await client.put(base, headers=headers, json={
                "embedding_model_id": str(embed.id),
                "rerank_model_id": str(rerank.id),
                "retrieval_config": {
                    "vector_top_k": 12,
                    "vector_weight": 0.8,
                    "keyword_weight": 0.2,
                },
            })
            assert response.json()["code"] == 0

            response = await client.put(base, headers=headers, json={
                "retrieval_config": {"vector_top_k": 9},
            })
            data = response.json()["data"]
            assert data["embedding_model"]["id"] == str(embed.id)
            assert data["rerank_model"]["id"] == str(rerank.id)
            assert data["values"]["vector_top_k"]["value"] == 9
            assert data["values"]["vector_weight"]["value"] == 0.8

            response = await client.put(base, headers=headers, json={
                "embedding_model_id": None,
            })
            data = response.json()["data"]
            assert data["embedding_model"] is None
            assert data["rerank_model"]["id"] == str(rerank.id)
            assert data["values"]["vector_top_k"]["value"] == 9

            response = await client.put(base, headers=headers, json={
                "rerank_model_id": None,
                "retrieval_config": None,
            })
            data = response.json()["data"]
            assert data["rerank_model"] is None
            assert data["values"]["vector_top_k"]["source"] == "system_default"
            assert data["values"]["vector_weight"]["source"] == "system_default"

            invalid_payloads = [
                {"embedding_model_id": str(llm.id)},
                {"embedding_model_id": str(bad_dim.id)},
                {"retrieval_config": {
                    "vector_weight": 0.2,
                    "keyword_weight": 0.5,
                }},
                {"retrieval_config": {"unknown_key": 1}},
            ]
            for payload in invalid_payloads:
                response = await client.put(base, headers=headers, json=payload)
                assert response.json()["code"] != 0

            other_headers = {"Authorization": f"Bearer {create_access_token(other_id)}"}
            response = await client.get(base, headers=other_headers)
            assert response.json()["code"] != 0
    finally:
        async with async_session() as s:
            await s.execute(delete(KnowledgeBase).where(
                KnowledgeBase.name == "PlanRetrievalSettingsApiKB"
            ))
            await s.execute(delete(ModelConfig).where(ModelConfig.name.like("plan_api_%")))
            await s.execute(delete(User).where(User.id == other_id))
            await s.commit()
