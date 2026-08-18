"""Document and chunk asset metadata API integration tests."""
import uuid
from urllib.parse import quote

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.db.session import async_session
from app.api.v2 import assets
from app.main import app
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.metadata import KbMetadataField
from app.models.user import User
from app.security.init_admin import ensure_admin
from app.security.jwt import create_access_token
from app.services import asset_service
from app.services.metadata_service import create_field, ensure_default_fields, update_field


async def _users() -> tuple[User, User]:
    await ensure_admin()
    async with async_session() as session:
        owner = (await session.execute(select(User).order_by(User.created_at))).scalars().first()
        username = "asset-metadata-second-user"
        other = (
            await session.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if other is None:
            other = User(
                username=username,
                hashed_password="not-for-login",
                is_active=True,
            )
            session.add(other)
            await session.commit()
        return owner, other


async def _kb(name: str, owner: User) -> str:
    async with async_session() as session:
        await session.execute(delete(KnowledgeBase).where(KnowledgeBase.name == name))
        kb = KnowledgeBase(user_id=owner.id, name=name, scene="general")
        session.add(kb)
        await session.commit()
        kb_id = str(kb.id)
    await ensure_default_fields(kb_id, user_id=owner.id)
    return kb_id


async def _make_document(
    kb_id: str,
    owner: User,
    name: str,
    *,
    metadata: dict | None = None,
    enabled: bool = True,
) -> str:
    async with async_session() as session:
        document = Document(
            kb_id=kb_id,
            user_id=owner.id,
            name=name,
            ext="pdf",
            size=128,
            status="done",
            pct=100,
            mode="fast",
            file_key=f"{kb_id}/{name}",
            metadata_=metadata or {},
            enabled=enabled,
        )
        session.add(document)
        await session.commit()
        return str(document.id)


async def _make_chunk(
    kb_id: str,
    document_id: str,
    seq: int,
    content: str,
    *,
    metadata: dict | None = None,
    enabled: bool = True,
) -> str:
    async with async_session() as session:
        chunk = Chunk(
            document_id=document_id,
            kb_id=kb_id,
            content=content,
            content_search=content,
            seq=seq,
            metadata_=metadata or {},
            enabled=enabled,
            char_count=len(content),
        )
        session.add(chunk)
        await session.commit()
        return str(chunk.id)


async def _field(kb_id: str, owner: User, **kwargs) -> str:
    field = await create_field(kb_id=kb_id, user_id=owner.id, **kwargs)
    return str(field.id)


async def _make_filterable(kb_id: str, owner: User, scope: str, key: str) -> None:
    async with async_session() as session:
        field = (
            await session.execute(
                select(KbMetadataField).where(
                    KbMetadataField.kb_id == kb_id,
                    KbMetadataField.scope == scope,
                    KbMetadataField.key == key,
                )
            )
        ).scalar_one()
    await update_field(field.id, user_id=owner.id, filterable=True)


@pytest.mark.asyncio
async def test_document_metadata_filter_and_batch_update():
    owner, _ = await _users()
    kb_id = await _kb("AssetMetadataDocumentKB", owner)
    doc_a_id = await _make_document(
        kb_id, owner, "招标文件.pdf", metadata={"source": "招标文件"}
    )
    doc_b_id = await _make_document(
        kb_id, owner, "投标文件.pdf", metadata={"source": "投标文件"}
    )
    await _make_filterable(kb_id, owner, "document", "source")
    headers = {"Authorization": f"Bearer {create_access_token(owner.id)}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get(
            f"/api/v2/documents?kb_id={kb_id}&document_metadata="
            + quote('{"source":"招标文件"}'),
            headers=headers,
        )
        assert response.json()["code"] == 0
        assert [item["name"] for item in response.json()["data"]["list"]] == [
            "招标文件.pdf"
        ]
        assert response.json()["data"]["list"][0]["metadata"]["document_name"] == "招标文件.pdf"
        assert response.json()["data"]["list"][0]["metadata"]["source"] == "招标文件"

        response = await client.post(
            "/api/v2/documents/batch-metadata",
            headers=headers,
            json={
                "ids": [doc_b_id],
                "metadata": {"source": "招标文件"},
            },
        )
        assert response.json()["code"] == 0
        assert response.json()["data"]["updated"] == 1

        response = await client.get(
            f"/api/v2/documents?kb_id={kb_id}&document_metadata="
            + quote('{"source":"招标文件"}'),
            headers=headers,
        )
        assert {item["id"] for item in response.json()["data"]["list"]} == {
            doc_a_id,
            doc_b_id,
        }


@pytest.mark.asyncio
async def test_chunk_metadata_and_enabled_filter():
    owner, _ = await _users()
    kb_id = await _kb("AssetMetadataChunkKB", owner)
    document_id = await _make_document(kb_id, owner, "条款文档.pdf")
    await _field(
        kb_id,
        owner,
        key="effective_status",
        name="生效状态",
        scope="chunk",
        data_type="select",
        options=["现行有效", "已废止"],
    )
    chunk_a_id = await _make_chunk(
        kb_id,
        document_id,
        1,
        "甲方应提供三年质检记录",
        metadata={"effective_status": "现行有效"},
    )
    chunk_b_id = await _make_chunk(
        kb_id,
        document_id,
        2,
        "乙方应提供履约保证金",
        metadata={"effective_status": "现行有效"},
    )
    headers = {"Authorization": f"Bearer {create_access_token(owner.id)}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.patch(
            f"/api/v2/chunks/{chunk_a_id}/metadata",
            headers=headers,
            json={"metadata": {"effective_status": "已废止"}},
        )
        assert response.json()["code"] == 0
        assert (
            response.json()["data"]["metadata"]["effective_status"] == "已废止"
        )

        response = await client.post(
            "/api/v2/chunks/batch-status",
            headers=headers,
            json={"ids": [chunk_b_id], "enabled": False},
        )
        assert response.json()["code"] == 0
        assert response.json()["data"]["updated"] == 1

        response = await client.get(
            f"/api/v2/chunks?kb_id={kb_id}&enabled=false", headers=headers
        )
        assert response.json()["code"] == 0
        assert response.json()["data"]["list"][0]["id"] == chunk_b_id
        assert response.json()["data"]["list"][0]["document_name"] == "条款文档.pdf"


@pytest.mark.asyncio
async def test_document_enabled_filter_and_batch_status():
    owner, _ = await _users()
    kb_id = await _kb("AssetMetadataDocumentStatusKB", owner)
    enabled_id = await _make_document(kb_id, owner, "enabled.pdf")
    disabled_id = await _make_document(
        kb_id, owner, "disabled.pdf", enabled=False
    )
    headers = {"Authorization": f"Bearer {create_access_token(owner.id)}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get(
            f"/api/v2/documents?kb_id={kb_id}&enabled=false", headers=headers
        )
        assert response.json()["code"] == 0
        assert [item["id"] for item in response.json()["data"]["list"]] == [disabled_id]

        response = await client.post(
            "/api/v2/documents/batch-status",
            headers=headers,
            json={"ids": [enabled_id, disabled_id], "enabled": False},
        )
        assert response.json()["code"] == 0
        assert response.json()["data"]["updated"] == 2

        response = await client.get(
            f"/api/v2/documents?kb_id={kb_id}&enabled=false", headers=headers
        )
        assert len(response.json()["data"]["list"]) == 2


@pytest.mark.asyncio
async def test_chunk_batch_metadata_and_parameter_bound_filters():
    owner, _ = await _users()
    kb_id = await _kb("AssetMetadataChunkBatchKB", owner)
    document_id = await _make_document(kb_id, owner, "批次文档.pdf")
    await _field(
        kb_id,
        owner,
        key="clause_type",
        name="条款类型",
        scope="chunk",
        data_type="select",
        options=["义务", "权利"],
        filterable=True,
    )
    chunk_a_id = await _make_chunk(
        kb_id, document_id, 1, "甲方义务", metadata={"clause_type": "义务"}
    )
    chunk_b_id = await _make_chunk(
        kb_id, document_id, 2, "乙方权利", metadata={"clause_type": "义务"}
    )
    headers = {"Authorization": f"Bearer {create_access_token(owner.id)}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.post(
            "/api/v2/chunks/batch-metadata",
            headers=headers,
            json={
                "ids": [chunk_a_id, chunk_b_id],
                "metadata": {"clause_type": "权利"},
            },
        )
        assert response.json()["code"] == 0
        assert response.json()["data"]["updated"] == 2

        response = await client.get(
            f"/api/v2/chunks?kb_id={kb_id}&document_id={document_id}"
            + "&chunk_metadata="
            + quote('{"clause_type":["义务","权利"]}')
            + "&vector_state=pending",
            headers=headers,
        )
        assert response.json()["code"] == 0
        assert {item["id"] for item in response.json()["data"]["list"]} == {
            chunk_a_id,
            chunk_b_id,
        }

@pytest.mark.asyncio
async def test_required_unknown_and_malformed_metadata_are_rejected():
    owner, _ = await _users()
    kb_id = await _kb("AssetMetadataValidationKB", owner)
    document_id = await _make_document(kb_id, owner, "required.pdf")
    chunk_id = await _make_chunk(kb_id, document_id, 1, "正文")
    await _field(
        kb_id,
        owner,
        key="project_code",
        name="项目编码",
        scope="document",
        data_type="string",
        required=True,
    )
    headers = {"Authorization": f"Bearer {create_access_token(owner.id)}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.patch(
            f"/api/v2/documents/{document_id}/metadata",
            headers=headers,
            json={"metadata": {"source": "合同"}},
        )
        assert response.json()["code"] == 40001

        response = await client.patch(
            f"/api/v2/documents/{document_id}/metadata",
            headers=headers,
            json={"metadata": {"project_code": "PRJ-001", "illegal_key": "x"}},
        )
        assert response.json()["code"] == 40001

        response = await client.patch(
            f"/api/v2/chunks/{chunk_id}/metadata",
            headers=headers,
            json={"metadata": {"effective_status": "现行有效"}},
        )
        assert response.json()["code"] == 40001

        response = await client.get(
            f"/api/v2/documents?kb_id={kb_id}&document_metadata=" + quote("{bad json"),
            headers=headers,
        )
        assert response.json()["code"] == 40001


@pytest.mark.asyncio
async def test_asset_access_and_mutation_require_ownership():
    owner, other = await _users()
    kb_id = await _kb("AssetMetadataOwnershipKB", owner)
    document_id = await _make_document(kb_id, owner, "owned.pdf")
    chunk_id = await _make_chunk(kb_id, document_id, 1, "owned content")
    owner_headers = {"Authorization": f"Bearer {create_access_token(owner.id)}"}
    other_headers = {"Authorization": f"Bearer {create_access_token(other.id)}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get(
            f"/api/v2/documents?kb_id={kb_id}&enabled=false", headers=other_headers
        )
        assert response.json()["code"] == 40300

        response = await client.get(
            f"/api/v2/chunks?kb_id={kb_id}", headers=other_headers
        )
        assert response.json()["code"] == 40300

        response = await client.patch(
            f"/api/v2/documents/{document_id}/metadata",
            headers=other_headers,
            json={"metadata": {"source": "other"}},
        )
        assert response.json()["code"] == 40300

        response = await client.post(
            "/api/v2/chunks/batch-status",
            headers=other_headers,
            json={"ids": [chunk_id], "enabled": False},
        )
        assert response.json()["code"] == 0
        assert response.json()["data"]["updated"] == 0

        response = await client.get(
            f"/api/v2/documents/{document_id}", headers=other_headers
        )
        assert response.json()["code"] == 40300

        response = await client.get(
            f"/api/v2/documents/{document_id}", headers=owner_headers
        )
        assert response.json()["code"] == 0


@pytest.mark.asyncio
async def test_list_chunks_queries_are_scoped_to_requested_kb(monkeypatch):
    kb_id = uuid.uuid4()
    user_id = uuid.uuid4()
    kb = KnowledgeBase(user_id=user_id)
    kb.id = kb_id

    class FakeResult:
        @staticmethod
        def scalar_one_or_none():
            return kb

        @staticmethod
        def scalar_one():
            return 0

        @staticmethod
        def all():
            return []

    class FakeSession:
        def __init__(self):
            self.queries = []

        async def execute(self, query):
            self.queries.append(query)
            return FakeResult()

    class FakeSessionContext:
        def __init__(self, session):
            self.session = session

        async def __aenter__(self):
            return self.session

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    session = FakeSession()
    monkeypatch.setattr(
        asset_service, "async_session", lambda: FakeSessionContext(session)
    )
    chunks, total = await asset_service.list_chunks(kb_id=kb_id, user_id=user_id)

    assert chunks == []
    assert total == 0
    assert len(session.queries) == 3
    for query in session.queries[1:]:
        sql = str(query)
        assert "knowledge_bases.id =" in sql
        assert "documents.kb_id =" in sql
        assert "chunks.kb_id =" in sql
        compiled = query.compile()
        assert any(str(value) == str(kb_id) for value in compiled.params.values())


def test_asset_routes_are_registered_without_database():
    included = any(
        getattr(route, "original_router", None) is assets.router
        for route in app.routes
    )
    assert included
    paths = {route.path for route in assets.router.routes}
    expected = {
        "/documents",
        "/documents/{doc_id}",
        "/documents/{doc_id}/metadata",
        "/documents/batch-metadata",
        "/documents/batch-status",
        "/chunks",
        "/chunks/{chunk_id}/metadata",
        "/chunks/batch-metadata",
        "/chunks/batch-status",
    }
    assert expected <= paths
