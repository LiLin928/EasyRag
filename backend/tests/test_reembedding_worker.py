"""KB-bound indexing and reindexing integration tests."""
import uuid
from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.api.v2 import assets
from app.api.deps import get_current_user
from app.db.session import async_session
from app.main import app
from app.models.chunk import Chunk
from app.models.document import Document, ParseTask
from app.models.knowledge_base import KnowledgeBase
from app.models.model_config import ModelConfig
from app.models.user import User
from app.security.init_admin import ensure_admin
from app.security.jwt import create_access_token
from app.worker.app import (
    WorkerSettings,
    parse_document_task,
    reembed_chunks_task,
)


async def _owner_and_other() -> tuple[User, User]:
    await ensure_admin()
    async with async_session() as session:
        owner = (
            await session.execute(select(User).order_by(User.created_at))
        ).scalars().first()
        other = (
            await session.execute(
                select(User).where(User.username == "reembedding-other-user")
            )
        ).scalar_one_or_none()
        if other is None:
            other = User(
                username="reembedding-other-user",
                hashed_password="not-for-login",
                is_active=True,
            )
            session.add(other)
            await session.commit()
        return owner, other


async def _embedding_model(name: str, *, enabled: bool = True) -> str:
    async with async_session() as session:
        await session.execute(delete(ModelConfig).where(ModelConfig.name == name))
        model = ModelConfig(
            grp="embed",
            name=name,
            prov="openai",
            use="retrieval",
            params={"dim": 1024},
            enabled=enabled,
        )
        session.add(model)
        await session.commit()
        return str(model.id)


async def _kb(
    name: str,
    owner: User,
    embedding_model_id: str | None = None,
) -> str:
    async with async_session() as session:
        await session.execute(delete(KnowledgeBase).where(KnowledgeBase.name == name))
        kb = KnowledgeBase(
            user_id=owner.id,
            name=name,
            scene="general",
            embedding_model_id=embedding_model_id,
        )
        session.add(kb)
        await session.commit()
        return str(kb.id)


async def _document(
    kb_id: str,
    owner: User,
    name: str,
    *,
    enabled: bool = True,
) -> str:
    async with async_session() as session:
        document = Document(
            kb_id=kb_id,
            user_id=owner.id,
            name=name,
            ext="md",
            size=64,
            status="done",
            pct=100,
            file_key=f"{kb_id}/{name}",
            enabled=enabled,
        )
        session.add(document)
        await session.commit()
        return str(document.id)


async def _chunk(
    kb_id: str,
    document_id: str,
    seq: int,
    content: str,
    *,
    embedding=None,
    embedding_model: str | None = None,
    enabled: bool = True,
    metadata: dict | None = None,
) -> str:
    async with async_session() as session:
        chunk = Chunk(
            kb_id=kb_id,
            document_id=document_id,
            seq=seq,
            content=content,
            content_search=content,
            embedding=embedding,
            embedding_model=embedding_model,
            enabled=enabled,
            metadata_=metadata or {},
            char_count=len(content),
        )
        session.add(chunk)
        await session.commit()
        return str(chunk.id)


@pytest.mark.asyncio
async def test_parse_chunks_use_kb_embedding_and_defaults(monkeypatch):
    owner, _ = await _owner_and_other()
    model_id = await _embedding_model("plan_embed_1024")
    kb_id = await _kb("ReembedParseKB", owner, model_id)

    async with async_session() as session:
        document = Document(
            kb_id=kb_id,
            user_id=owner.id,
            name="terms.md",
            ext="md",
            size=64,
            status="pending",
            file_key=f"{kb_id}/terms.md",
        )
        session.add(document)
        await session.flush()
        task = ParseTask(doc_id=document.id, kb_id=kb_id, status="pending")
        session.add(task)
        await session.commit()
        doc_id = str(document.id)

    storage = AsyncMock()
    storage.get = AsyncMock(return_value=b"# Terms\nthree-year warranty")
    monkeypatch.setattr("app.worker.app.get_storage", lambda: storage)

    embeddings = AsyncMock()
    embeddings.aembed_documents = AsyncMock(return_value=[[0.2] * 1024])
    build = AsyncMock(return_value=embeddings)
    monkeypatch.setattr("app.worker.app.build_embeddings_from_config", build)

    await parse_document_task({}, doc_id)

    async with async_session() as session:
        chunks = (
            await session.execute(select(Chunk).where(Chunk.document_id == doc_id))
        ).scalars().all()
        assert len(chunks) == 1
        assert chunks[0].embedding == [0.2] * 1024
        assert chunks[0].embedding_model == "plan_embed_1024"
        assert chunks[0].char_count == len(chunks[0].content)
        assert chunks[0].metadata_ == {}

    build.assert_awaited_once()
    assert str(build.call_args.args[0].id) == model_id


@pytest.mark.asyncio
async def test_parse_document_fails_readably_when_kb_model_is_disabled(monkeypatch):
    owner, _ = await _owner_and_other()
    model_id = await _embedding_model("plan_embed_disabled", enabled=False)
    kb_id = await _kb("ReembedDisabledModelKB", owner, model_id)

    async with async_session() as session:
        document = Document(
            kb_id=kb_id,
            user_id=owner.id,
            name="disabled-model.md",
            ext="md",
            size=64,
            status="pending",
            file_key=f"{kb_id}/disabled-model.md",
        )
        session.add(document)
        await session.flush()
        task = ParseTask(doc_id=document.id, kb_id=kb_id, status="pending")
        session.add(task)
        await session.commit()
        doc_id = str(document.id)

    storage = AsyncMock()
    storage.get = AsyncMock(return_value=b"# Terms\nwarranty")
    monkeypatch.setattr("app.worker.app.get_storage", lambda: storage)

    with pytest.raises(Exception):
        await parse_document_task({}, doc_id)

    async with async_session() as session:
        document = await session.get(Document, doc_id)
        task = (
            await session.execute(select(ParseTask).where(ParseTask.doc_id == doc_id))
        ).scalar_one()
        assert document.status == "failed"
        assert document.pct == 100
        assert "知识库绑定的 Embedding 模型不可用" in document.error
        assert task.status == "failed"
        assert task.error == document.error


@pytest.mark.asyncio
async def test_reembed_only_selected_chunks_in_batches_of_32(monkeypatch):
    owner, _ = await _owner_and_other()
    model_id = await _embedding_model("plan_embed_1024_v2")
    kb_id = await _kb("ReembedSelectiveKB", owner, model_id)
    doc_a_id = await _document(
        kb_id, owner, "selected.pdf", enabled=False
    )
    doc_b_id = await _document(kb_id, owner, "unselected.pdf")

    selected_ids = []
    for seq in range(1, 34):
        selected_ids.append(
            await _chunk(
                kb_id,
                doc_a_id,
                seq,
                f"selected chunk {seq}",
                embedding=[0.1] * 1024,
                embedding_model="plan_embed_1024",
                enabled=seq % 2 == 0,
            )
        )
    other_id = await _chunk(
        kb_id,
        doc_b_id,
        1,
        "other chunk",
        embedding=[0.1] * 1024,
        embedding_model="plan_embed_1024",
    )

    batch_sizes = []

    async def embed_documents(texts):
        batch_sizes.append(len(texts))
        assert len(texts) <= 32
        return [[0.9] * 1024 for _ in texts]

    embeddings = AsyncMock()
    embeddings.aembed_documents = embed_documents
    monkeypatch.setattr(
        "app.worker.app.build_embeddings_from_config",
        AsyncMock(return_value=embeddings),
    )

    await reembed_chunks_task({}, kb_id, selected_ids, [])

    assert batch_sizes == [32, 1]
    async with async_session() as session:
        selected = (
            await session.execute(
                select(Chunk).where(Chunk.id.in_(selected_ids)).order_by(Chunk.seq)
            )
        ).scalars().all()
        other = await session.get(Chunk, other_id)
        document_a = await session.get(Document, doc_a_id)
        document_b = await session.get(Document, doc_b_id)

    assert len(selected) == 33
    assert all(chunk.embedding == [0.9] * 1024 for chunk in selected)
    assert all(
        chunk.embedding_model == "plan_embed_1024_v2" for chunk in selected
    )
    assert [chunk.enabled for chunk in selected] == [
        seq % 2 == 0 for seq in range(1, 34)
    ]
    assert other.embedding == [0.1] * 1024
    assert other.embedding_model == "plan_embed_1024"
    assert document_a.enabled is False
    assert document_b.enabled is True


@pytest.mark.asyncio
async def test_reembed_empty_selectors_cover_only_requested_kb(monkeypatch):
    owner, _ = await _owner_and_other()
    target_model_id = await _embedding_model("plan_embed_target")
    other_model_id = await _embedding_model("plan_embed_other")
    target_kb_id = await _kb("ReembedTargetKB", owner, target_model_id)
    other_kb_id = await _kb("ReembedOtherKB", owner, other_model_id)
    target_doc_id = await _document(target_kb_id, owner, "target.md")
    other_doc_id = await _document(other_kb_id, owner, "other.md")
    target_chunk_id = await _chunk(
        target_kb_id,
        target_doc_id,
        1,
        "target content",
        embedding=[0.1] * 1024,
    )
    other_chunk_id = await _chunk(
        other_kb_id,
        other_doc_id,
        1,
        "other content",
        embedding=[0.1] * 1024,
    )

    embeddings = AsyncMock()
    embeddings.aembed_documents = AsyncMock(return_value=[[0.8] * 1024])
    monkeypatch.setattr(
        "app.worker.app.build_embeddings_from_config",
        AsyncMock(return_value=embeddings),
    )

    await reembed_chunks_task({}, target_kb_id, [], [])

    async with async_session() as session:
        target = await session.get(Chunk, target_chunk_id)
        other = await session.get(Chunk, other_chunk_id)
    assert target.embedding == [0.8] * 1024
    assert target.embedding_model == "plan_embed_target"
    assert other.embedding == [0.1] * 1024
    assert other.embedding_model is None


@pytest.mark.asyncio
async def test_reembed_api_validates_ownership_and_selectors(monkeypatch):
    owner, other = await _owner_and_other()
    kb_id = await _kb("ReembedAPIKB", owner)
    doc_id = await _document(kb_id, owner, "api.pdf")
    await _chunk(kb_id, doc_id, 1, "api content")

    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()
    monkeypatch.setattr("app.api.v2.assets.create_pool", AsyncMock(return_value=pool))
    owner_headers = {"Authorization": f"Bearer {create_access_token(owner.id)}"}
    other_headers = {"Authorization": f"Bearer {create_access_token(other.id)}"}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t"
    ) as client:
        response = await client.post(
            "/api/v2/chunks/reembed",
            headers=owner_headers,
            json={"kb_id": kb_id, "document_ids": [doc_id]},
        )
        assert response.json() == {
            "code": 0,
            "message": "success",
            "data": {"queued": True},
        }
        pool.enqueue_job.assert_called_once_with(
            "reembed_chunks_task", kb_id, [doc_id], []
        )

        response = await client.post(
            "/api/v2/chunks/reembed",
            headers=other_headers,
            json={"kb_id": kb_id, "document_ids": [doc_id]},
        )
        assert response.json()["code"] == 40300
        assert response.json()["message"] == "无权访问该知识库"
        pool.enqueue_job.assert_called_once()

        response = await client.post(
            "/api/v2/chunks/reembed",
            headers=owner_headers,
            json={
                "kb_id": kb_id,
                "document_ids": ["not-a-uuid"],
                "chunk_ids": ["also-not-a-uuid"],
            },
        )
        assert response.json()["code"] == 40001
        pool.enqueue_job.assert_called_once()


@pytest.mark.asyncio
async def test_reembed_api_rejects_invalid_selectors_with_api_envelope(monkeypatch):
    pool = AsyncMock()
    pool.enqueue_job = AsyncMock()
    monkeypatch.setattr("app.api.v2.assets.create_pool", AsyncMock(return_value=pool))
    headers = {
        "Authorization": f"Bearer {create_access_token(uuid.uuid4())}"
    }
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=uuid.uuid4()
    )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            response = await client.post(
                "/api/v2/chunks/reembed",
                headers=headers,
                json={"kb_id": str(uuid.uuid4()), "document_ids": ["not-a-uuid"]},
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.json() == {
        "code": 40001,
        "message": "无效的文档 ID",
        "data": None,
    }
    pool.enqueue_job.assert_not_called()


def test_reembed_worker_and_route_are_registered():
    assert reembed_chunks_task in WorkerSettings.functions
    paths = {route.path for route in assets.router.routes}
    assert "/chunks/reembed" in paths
