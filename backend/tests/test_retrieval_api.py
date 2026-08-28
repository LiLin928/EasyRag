"""Retrieval debug API tests."""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.api.deps import get_current_user
from app.core.retrieval.metadata_filter import MetadataFilter
from app.core.retrieval.pipeline import RetrievalResult
from app.db.session import async_session
from app.main import app
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.metadata import KbMetadataField
from app.models.user import User
from app.security.init_admin import ensure_admin
from app.security.jwt import create_access_token
from app.services.retrieval_settings_service import SYSTEM_DEFAULTS
from app.exceptions import BizException, ErrorCode


def _effective():
    return {
        "values": {
            "method": {"value": "hybrid", "source": "system_default"},
            "final_top_k": {"value": 5, "source": "system_default"},
        },
        "resolved": {"method": "hybrid", "final_top_k": 5},
        "embedding_model": {"id": "embed-model"},
        "rerank_model": {"id": "rerank-model"},
    }


@pytest.mark.asyncio
async def test_search_api_resolves_kb_and_passes_pipeline_contract():
    captured = {}

    class FakePipeline:
        def __init__(self, *, settings, embedding_model=None, rerank_model=None):
            captured["settings"] = settings
            captured["embedding_model"] = embedding_model
            captured["rerank_model"] = rerank_model

        async def search(self, query, **kwargs):
            captured["query"] = query
            captured["search"] = kwargs
            return RetrievalResult(chunks=[{"id": "one"}])

    source_field = KbMetadataField(
        key="source", scope="document", data_type="string", retrieval_filterable=True
    )
    status_field = KbMetadataField(
        key="effective_status",
        scope="chunk",
        data_type="select",
        options=["现行有效"],
        retrieval_filterable=True,
    )

    async def fake_list_fields(kb_id, user_id, scope=None):
        captured["schema_scope"] = scope
        if scope == "document":
            return [source_field]
        if scope == "chunk":
            return [status_field]
        return []

    app.dependency_overrides[get_current_user] = lambda: type(
        "User", (), {"id": "00000000-0000-0000-0000-000000000001"}
    )()
    try:
        with patch(
            "app.api.v2.retrieval.get_effective_settings",
            AsyncMock(return_value=_effective()),
        ), patch(
            "app.api.v2.retrieval.metadata_service.list_fields",
            AsyncMock(side_effect=fake_list_fields),
        ), patch(
            "app.api.v2.retrieval.metadata_service.require_owned_kbs",
            AsyncMock(),
        ), patch(
            "app.api.v2.retrieval.RetrievalPipeline", FakePipeline
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v2/search",
                    json={
                        "kb_ids": ["00000000-0000-0000-0000-000000000010"],
                        "document_ids": ["00000000-0000-0000-0000-000000000020"],
                        "question": "q",
                        "top_k": 7,
                        "override_config": {"method": "vector"},
                        "document_metadata": {"source": "招标文件"},
                        "chunk_metadata": {"effective_status": "现行有效"},
                    },
                )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.json() == {
        "code": 0,
        "message": "success",
        "data": {
            "results": [{"id": "one"}],
            "rerank_triggered": False,
            "rerank_skipped_reason": None,
            "mode": "hybrid",
            "nav_info": None,
        },
    }
    assert captured["settings"] == _effective()
    assert captured["embedding_model"] == {"id": "embed-model"}
    assert captured["rerank_model"] == {"id": "rerank-model"}
    assert captured["query"] == "q"
    assert captured["search"] == {
        "kb_ids": ["00000000-0000-0000-0000-000000000010"],
        "doc_ids": ["00000000-0000-0000-0000-000000000020"],
        "scope": None,
        "metadata_filter": MetadataFilter(
            document={"source": "招标文件"},
            chunk={"effective_status": "现行有效"},
        ),
        "top_k": 7,
        "enable_nav": None,
        "count_recall": False,
    }


@pytest.mark.asyncio
async def test_search_api_without_kb_keeps_system_defaults():
    captured = {}

    class FakePipeline:
        def __init__(self, *, settings, embedding_model=None, rerank_model=None):
            captured["settings"] = settings
            captured["models"] = (embedding_model, rerank_model)

        async def search(self, query, **kwargs):
            captured["search"] = kwargs
            return RetrievalResult(chunks=[])

    app.dependency_overrides[get_current_user] = lambda: type(
        "User", (), {"id": "00000000-0000-0000-0000-000000000001"}
    )()
    try:
        with patch(
            "app.api.v2.retrieval.get_effective_settings", AsyncMock()
        ) as effective, patch(
            "app.api.v2.retrieval.RetrievalPipeline", FakePipeline
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v2/search",
                    json={"question": "q", "document_ids": ["d1"]},
                )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.json()["code"] == 0
    effective.assert_not_called()
    assert captured["settings"]["resolved"] == SYSTEM_DEFAULTS
    assert captured["models"] == (None, None)
    assert captured["search"]["kb_ids"] == []
    assert captured["search"]["doc_ids"] == ["d1"]
    assert captured["search"]["count_recall"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "list_fields"),
    [
        (
            {
                "kb_ids": [
                    "00000000-0000-0000-0000-000000000010",
                    "00000000-0000-0000-0000-000000000011",
                ],
                "question": "q",
            },
            False,
        ),
        (
            {
                "kb_ids": [
                    "00000000-0000-0000-0000-000000000010",
                    "00000000-0000-0000-0000-000000000011",
                ],
                "question": "q",
                "document_metadata": {"source": "招标文件"},
            },
            True,
        ),
    ],
)
async def test_search_api_authorizes_every_multi_kb_before_retrieval(
    payload, list_fields
):
    class FailingPipeline:
        def __init__(self, **kwargs):
            raise AssertionError("retrieval must not run without KB authorization")

    app.dependency_overrides[get_current_user] = lambda: type(
        "User", (), {"id": "00000000-0000-0000-0000-000000000001"}
    )()
    try:
        with patch(
            "app.api.v2.retrieval.metadata_service.require_owned_kbs",
            AsyncMock(
                side_effect=BizException(ErrorCode.FORBIDDEN, "无权访问该知识库")
            ),
        ) as authorize, patch(
            "app.api.v2.retrieval.metadata_service.list_fields", AsyncMock()
        ) as fields, patch(
            "app.api.v2.retrieval.RetrievalPipeline", FailingPipeline
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/api/v2/search", json=payload)
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.json()["code"] == int(ErrorCode.FORBIDDEN)
    authorize.assert_awaited_once_with(
        payload["kb_ids"], "00000000-0000-0000-0000-000000000001"
    )
    if not list_fields:
        fields.assert_not_called()


@pytest.mark.asyncio
async def test_search_api_lets_resolved_settings_disable_navigation():
    captured = {}

    class FakePipeline:
        def __init__(self, *, settings, embedding_model=None, rerank_model=None):
            captured["settings"] = settings

        async def search(self, query, **kwargs):
            captured["search"] = kwargs
            return RetrievalResult(chunks=[])

    app.dependency_overrides[get_current_user] = lambda: type(
        "User", (), {"id": "00000000-0000-0000-0000-000000000001"}
    )()
    try:
        with patch("app.api.v2.retrieval.RetrievalPipeline", FakePipeline):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v2/search",
                    json={
                        "question": "q",
                        "document_ids": ["00000000-0000-0000-0000-000000000020"],
                        "override_config": {"navigation_enabled": False},
                    },
                )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.json()["code"] == 0
    assert captured["settings"]["resolved"]["navigation_enabled"] is False
    assert captured["search"]["enable_nav"] is None


@pytest.mark.asyncio
async def test_search_api_excludes_disabled_documents_and_chunks():
    await ensure_admin()
    async with async_session() as s:
        await s.execute(
            delete(KnowledgeBase).where(KnowledgeBase.name == "RetrievalDisabledKB")
        )
        await s.commit()
        user = (await s.execute(select(User))).scalars().first()
        kb = KnowledgeBase(user_id=user.id, name="RetrievalDisabledKB", scene="general")
        s.add(kb)
        await s.flush()
        enabled_doc = Document(
            kb_id=kb.id,
            user_id=user.id,
            name="enabled.pdf",
            ext="pdf",
            size=1,
            file_key="retrieval/enabled.pdf",
            enabled=True,
        )
        disabled_doc = Document(
            kb_id=kb.id,
            user_id=user.id,
            name="disabled.pdf",
            ext="pdf",
            size=1,
            file_key="retrieval/disabled.pdf",
            enabled=False,
        )
        s.add_all([enabled_doc, disabled_doc])
        await s.flush()
        s.add_all(
            [
                Chunk(
                    document_id=enabled_doc.id,
                    kb_id=str(kb.id),
                    content="warranty enabled document",
                    content_search="warranty enabled document",
                    seq=1,
                    enabled=True,
                ),
                Chunk(
                    document_id=enabled_doc.id,
                    kb_id=str(kb.id),
                    content="warranty disabled chunk",
                    content_search="warranty disabled chunk",
                    seq=2,
                    enabled=False,
                ),
                Chunk(
                    document_id=disabled_doc.id,
                    kb_id=str(kb.id),
                    content="warranty disabled document",
                    content_search="warranty disabled document",
                    seq=3,
                    enabled=True,
                ),
            ]
        )
        await s.commit()
        kb_id = str(kb.id)
        token = create_access_token(user.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        response = await c.post(
            "/api/v2/search",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "kb_ids": [kb_id],
                "question": "warranty",
                "override_config": {
                    "method": "keyword",
                    "navigation_enabled": False,
                    "rerank_enabled": False,
                },
            },
        )

    assert response.json()["code"] == 0
    results = response.json()["data"]["results"]
    assert [item["content"] for item in results] == ["warranty enabled document"]
