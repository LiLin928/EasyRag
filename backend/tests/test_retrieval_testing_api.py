"""Retrieval test set and case API integration tests."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.api.v2 import retrieval_testing
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.main import app
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.metadata import KbMetadataField
from app.models.model_config import ModelConfig
from app.models.retrieval_testing import (
    RetrievalTestCase,
    RetrievalTestCaseResult,
    RetrievalTestRun,
    RetrievalTestSet,
)
from app.models.user import User
from app.security.jwt import create_access_token


async def _seed(*, with_other_kb: bool = False) -> SimpleNamespace:
    suffix = uuid.uuid4().hex[:10]
    owner = User(
        username=f"rt-owner-{suffix}",
        hashed_password="not-for-login",
        is_active=True,
    )
    other = User(
        username=f"rt-other-{suffix}",
        hashed_password="not-for-login",
        is_active=True,
    )
    async with async_session() as session:
        session.add_all([owner, other])
        await session.flush()
        kb = KnowledgeBase(
            user_id=owner.id,
            name=f"Retrieval Testing KB {suffix}",
            scene="general",
        )
        other_kb = KnowledgeBase(
            user_id=owner.id,
            name=f"Retrieval Testing Other KB {suffix}",
            scene="general",
        )
        session.add_all([kb, other_kb] if with_other_kb else [kb])
        await session.flush()
        document = Document(
            kb_id=kb.id,
            user_id=owner.id,
            name="expected.pdf",
            ext="pdf",
            size=128,
            status="done",
            pct=100,
            mode="fast",
            file_key=f"{kb.id}/expected.pdf",
        )
        other_document = Document(
            kb_id=other_kb.id,
            user_id=owner.id,
            name="other-kb.pdf",
            ext="pdf",
            size=128,
            status="done",
            pct=100,
            mode="fast",
            file_key=f"{other_kb.id}/other-kb.pdf",
        )
        session.add_all([document, other_document] if with_other_kb else [document])
        await session.commit()
        return SimpleNamespace(
            owner_id=owner.id,
            other_id=other.id,
            kb_id=kb.id,
            other_kb_id=other_kb.id if with_other_kb else None,
            document_id=document.id,
            other_document_id=other_document.id if with_other_kb else None,
        )


async def _cleanup(seed: SimpleNamespace) -> None:
    kb_ids = [seed.kb_id]
    if seed.other_kb_id:
        kb_ids.append(seed.other_kb_id)
    async with async_session() as session:
        await session.execute(
            delete(RetrievalTestSet).where(RetrievalTestSet.kb_id.in_(kb_ids))
        )
        await session.execute(
            delete(Document).where(Document.kb_id.in_(kb_ids))
        )
        await session.execute(
            delete(KnowledgeBase).where(KnowledgeBase.id.in_(kb_ids))
        )
        await session.execute(
            delete(User).where(User.id.in_([seed.owner_id, seed.other_id]))
        )
        await session.commit()


def _headers(seed: SimpleNamespace, *, other: bool = False) -> dict:
    user_id = seed.other_id if other else seed.owner_id
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.mark.asyncio
async def test_create_update_batch_and_list_cases():
    seed = await _seed()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            response = await client.post(
                f"/api/v2/knowledge/{seed.kb_id}/retrieval-test-sets",
                headers=_headers(seed),
                json={"name": "Contract regression", "description": "V1 cases"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["code"] == 0
            test_set = body["data"]
            assert test_set["kb_id"] == str(seed.kb_id)
            assert test_set["archived"] is False

            response = await client.post(
                f"/api/v2/retrieval-test-sets/{test_set['id']}/cases",
                headers=_headers(seed),
                json={
                    "query": "liability cap",
                    "expected_doc_ids": [str(seed.document_id)],
                    "expected_chunk_ids": ["chunk-1"],
                    "tags": ["contract", "liability"],
                    "sort_order": 2,
                },
            )
            assert response.json()["code"] == 0
            case = response.json()["data"]
            assert case["query"] == "liability cap"
            assert case["expected_doc_ids"] == [str(seed.document_id)]
            assert case["expected_chunk_ids"] == ["chunk-1"]
            assert case["enabled"] is True
            assert not {"first_expected_hit_rank", "status", "latency_ms", "last_run_at"}.intersection(case)

            response = await client.put(
                f"/api/v2/retrieval-test-cases/{case['id']}",
                headers=_headers(seed),
                json={"query": "updated liability cap", "tags": ["regression"]},
            )
            assert response.json()["code"] == 0
            assert response.json()["data"]["query"] == "updated liability cap"
            assert response.json()["data"]["tags"] == ["regression"]

            response = await client.post(
                "/api/v2/retrieval-test-cases/batch-status",
                headers=_headers(seed),
                json={"ids": [case["id"]], "enabled": False},
            )
            assert response.json()["code"] == 0
            assert response.json()["data"]["updated"] == 1

            response = await client.get(
                f"/api/v2/retrieval-test-sets/{test_set['id']}/cases",
                headers=_headers(seed),
            )
            assert response.json()["data"] == {
                "list": [response.json()["data"]["list"][0]],
                "total": 1,
            }
            listed_case = response.json()["data"]["list"][0]
            assert listed_case["id"] == case["id"]
            assert listed_case["enabled"] is False
    finally:
        await _cleanup(seed)


@pytest.mark.asyncio
async def test_case_and_test_set_validation_rules():
    seed = await _seed(with_other_kb=True)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            response = await client.post(
                f"/api/v2/knowledge/{seed.kb_id}/retrieval-test-sets",
                headers=_headers(seed),
                json={"name": "Valid set"},
            )
            assert response.json()["code"] == 0
            set_id = response.json()["data"]["id"]

            invalid_payloads = [
                {
                    "query": "  ",
                    "expected_doc_ids": [str(seed.document_id)],
                },
                {
                    "query": "cross-KB expected document",
                    "expected_doc_ids": [str(seed.other_document_id)],
                },
                {
                    "query": "too many tags",
                    "expected_doc_ids": [],
                    "tags": [f"tag-{index}" for index in range(21)],
                },
                {
                    "query": "duplicate tags",
                    "expected_doc_ids": [],
                    "tags": ["same", "same"],
                },
            ]
            for payload in invalid_payloads:
                response = await client.post(
                    f"/api/v2/retrieval-test-sets/{set_id}/cases",
                    headers=_headers(seed),
                    json=payload,
                )
                assert response.json()["code"] == 40001

            response = await client.post(
                f"/api/v2/knowledge/{seed.kb_id}/retrieval-test-sets",
                headers=_headers(seed),
                json={"name": "x" * 101},
            )
            assert response.json()["code"] == 40001
    finally:
        await _cleanup(seed)


@pytest.mark.asyncio
async def test_set_and_case_access_require_owner():
    seed = await _seed()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            response = await client.post(
                f"/api/v2/knowledge/{seed.kb_id}/retrieval-test-sets",
                headers=_headers(seed),
                json={"name": "Owned set"},
            )
            set_id = response.json()["data"]["id"]
            response = await client.post(
                f"/api/v2/retrieval-test-sets/{set_id}/cases",
                headers=_headers(seed),
                json={"query": "owned query"},
            )
            case_id = response.json()["data"]["id"]

            for method, path in [
                ("GET", f"/api/v2/retrieval-test-sets/{set_id}"),
                ("PUT", f"/api/v2/retrieval-test-sets/{set_id}"),
                ("GET", f"/api/v2/retrieval-test-sets/{set_id}/cases"),
                ("PUT", f"/api/v2/retrieval-test-cases/{case_id}"),
                ("GET", f"/api/v2/retrieval-test-sets/{set_id}/runs"),
            ]:
                response = await getattr(client, method.lower())(
                    path,
                    headers=_headers(seed, other=True),
                    json={"name": "Forbidden update"} if method == "PUT" else None,
                )
                assert response.json()["code"] == 40300
    finally:
        await _cleanup(seed)


@pytest.mark.asyncio
async def test_delete_set_cascades_cases_in_database():
    seed = await _seed()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            response = await client.post(
                f"/api/v2/knowledge/{seed.kb_id}/retrieval-test-sets",
                headers=_headers(seed),
                json={"name": "Cascade set"},
            )
            set_id = response.json()["data"]["id"]
            response = await client.post(
                f"/api/v2/retrieval-test-sets/{set_id}/cases",
                headers=_headers(seed),
                json={"query": "cascade query"},
            )
            case_id = response.json()["data"]["id"]

            response = await client.delete(
                f"/api/v2/retrieval-test-sets/{set_id}",
                headers=_headers(seed),
            )
            assert response.json()["code"] == 0

        async with async_session() as session:
            cases = (
                await session.execute(
                    select(RetrievalTestCase).where(
                        RetrievalTestCase.id == uuid.UUID(case_id)
                    )
                )
            ).scalars().all()
        assert cases == []
    finally:
        await _cleanup(seed)


@pytest.mark.asyncio
async def test_archived_sets_are_hidden_unless_requested():
    seed = await _seed()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            response = await client.post(
                f"/api/v2/knowledge/{seed.kb_id}/retrieval-test-sets",
                headers=_headers(seed),
                json={"name": "Active set"},
            )
            active_id = response.json()["data"]["id"]
            response = await client.post(
                f"/api/v2/knowledge/{seed.kb_id}/retrieval-test-sets",
                headers=_headers(seed),
                json={"name": "Archived set"},
            )
            archived_id = response.json()["data"]["id"]
            response = await client.put(
                f"/api/v2/retrieval-test-sets/{archived_id}",
                headers=_headers(seed),
                json={"archived": True},
            )
            assert response.json()["data"]["archived"] is True

            response = await client.get(
                f"/api/v2/knowledge/{seed.kb_id}/retrieval-test-sets",
                headers=_headers(seed),
            )
            assert response.json()["data"]["total"] == 1
            assert response.json()["data"]["list"][0]["id"] == active_id

            response = await client.get(
                f"/api/v2/knowledge/{seed.kb_id}/retrieval-test-sets?include_archived=true",
                headers=_headers(seed),
            )
            assert response.json()["data"]["total"] == 2
            assert {item["id"] for item in response.json()["data"]["list"]} == {
                active_id,
                archived_id,
            }
    finally:
        await _cleanup(seed)


@pytest.mark.asyncio
async def test_run_history_is_initially_empty():
    seed = await _seed()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            response = await client.post(
                f"/api/v2/knowledge/{seed.kb_id}/retrieval-test-sets",
                headers=_headers(seed),
                json={"name": "Run history set"},
            )
            set_id = response.json()["data"]["id"]
            response = await client.get(
                f"/api/v2/retrieval-test-sets/{set_id}/runs",
                headers=_headers(seed),
            )
            assert response.status_code == 200
            assert response.json()["data"] == {"list": [], "total": 0}
    finally:
        await _cleanup(seed)


@pytest.mark.asyncio
async def test_start_run_creates_snapshot_and_results(monkeypatch):
    suffix = uuid.uuid4().hex[:10]
    seed = await _seed()
    async with async_session() as session:
        embed = ModelConfig(
            grp="embed",
            name=f"rt-embed-{suffix}",
            prov="openai",
            use="retrieval",
            url="http://embedding.invalid",
            api_key_enc="secret",
            params={"dim": 1024},
            enabled=True,
        )
        rerank = ModelConfig(
            grp="rerank",
            name=f"rt-rerank-{suffix}",
            prov="openai",
            use="rerank",
            url="http://rerank.invalid",
            api_key_enc="secret",
            params={},
            enabled=True,
        )
        session.add_all([embed, rerank])
        await session.flush()
        kb = await session.get(KnowledgeBase, seed.kb_id)
        kb.embedding_model_id = embed.id
        kb.rerank_model_id = rerank.id
        session.add_all(
            [
                KbMetadataField(
                    kb_id=kb.id,
                    key="source",
                    name="Source",
                    scope="document",
                    data_type="select",
                    options=["招标文件"],
                    retrieval_filterable=True,
                ),
                KbMetadataField(
                    kb_id=kb.id,
                    key="effective_status",
                    name="Status",
                    scope="chunk",
                    data_type="select",
                    options=["现行有效"],
                    retrieval_filterable=True,
                ),
            ]
        )
        await session.commit()

    fake_pool = AsyncMock()
    monkeypatch.setattr(
        "app.api.v2.retrieval_testing.create_pool",
        AsyncMock(return_value=fake_pool),
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            response = await client.post(
                f"/api/v2/knowledge/{seed.kb_id}/retrieval-test-sets",
                headers=_headers(seed),
                json={"name": "Async regression"},
            )
            set_id = response.json()["data"]["id"]
            for query, expected in [
                ("liability cap", [str(seed.document_id)]),
                ("termination", ["00000000-0000-0000-0000-000000000099"]),
            ]:
                response = await client.post(
                    f"/api/v2/retrieval-test-sets/{set_id}/cases",
                    headers=_headers(seed),
                    json={"query": query, "expected_doc_ids": expected},
                )
                assert response.json()["code"] == 0

            response = await client.post(
                f"/api/v2/retrieval-test-sets/{set_id}/runs",
                headers=_headers(seed),
                json={
                    "case_ids": [],
                    "ks": [3, 5],
                    "override_config": {"vector_top_k": 9},
                    "document_metadata": {"source": ["招标文件"]},
                    "chunk_metadata": {"effective_status": ["现行有效"]},
                },
            )
            body = response.json()
            assert body["code"] == 0
            assert body["data"]["status"] == "pending"
            assert body["data"]["total_cases"] == 2
            assert (
                body["data"]["config_snapshot"]["settings"]["resolved"]["vector_top_k"]
                == 9
            )
            assert body["data"]["config_snapshot"]["document_metadata"]["source"] == [
                "招标文件"
            ]
            assert body["data"]["config_snapshot"]["embedding_model"] == {
                "id": body["data"]["config_snapshot"]["embedding_model"]["id"],
                "name": f"rt-embed-{suffix}",
                "prov": "openai",
                "dim": 1024,
            }
            assert "url" not in str(body["data"]["config_snapshot"])
            assert "api_key" not in str(body["data"]["config_snapshot"])
            fake_pool.enqueue_job.assert_called_once_with(
                "run_retrieval_test_task", body["data"]["id"]
            )

            response = await client.post(
                f"/api/v2/retrieval-test-sets/{set_id}/runs",
                headers=_headers(seed),
                json={},
            )
            assert response.json()["code"] == 0
            assert response.json()["data"]["id"] == body["data"]["id"]
            fake_pool.enqueue_job.assert_called_once()
    finally:
        async with async_session() as session:
            run_ids = (
                await session.execute(
                    select(RetrievalTestRun.id).where(
                        RetrievalTestRun.kb_id == seed.kb_id
                    )
                )
            ).scalars().all()
            if run_ids:
                await session.execute(
                    delete(RetrievalTestCaseResult).where(
                        RetrievalTestCaseResult.run_id.in_(run_ids)
                    )
                )
                await session.execute(
                    delete(RetrievalTestRun).where(RetrievalTestRun.id.in_(run_ids))
                )
            await session.execute(
                delete(ModelConfig).where(
                    ModelConfig.name.in_([f"rt-embed-{suffix}", f"rt-rerank-{suffix}"])
                )
            )
            await session.commit()
        await _cleanup(seed)


@pytest.mark.asyncio
async def test_run_validation_rules(monkeypatch):
    seed = await _seed()
    monkeypatch.setattr(
        "app.api.v2.retrieval_testing.create_pool", AsyncMock(return_value=AsyncMock())
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            response = await client.post(
                f"/api/v2/knowledge/{seed.kb_id}/retrieval-test-sets",
                headers=_headers(seed),
                json={"name": "Validation runs"},
            )
            set_id = response.json()["data"]["id"]
            for payload in (
                {},
                {"ks": []},
                {"ks": [3, 3]},
                {"ks": [3, "5"]},
                {"ks": [101]},
                {"override_config": {"unknown": 1}},
            ):
                response = await client.post(
                    f"/api/v2/retrieval-test-sets/{set_id}/runs",
                    headers=_headers(seed),
                    json=payload,
                )
                assert response.json()["code"] == 40001
    finally:
        await _cleanup(seed)


@pytest.mark.asyncio
async def test_run_routes_use_service_ownership_and_hide_pending_internals(
    monkeypatch,
):
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    run_id = uuid.uuid4()
    forbidden = BizException(ErrorCode.FORBIDDEN, "Retrieval test run not accessible")
    run = SimpleNamespace(id=str(run_id), status="running")
    result = SimpleNamespace(id=str(uuid.uuid4()), status="running")

    monkeypatch.setattr(
        retrieval_testing.service,
        "get_run",
        AsyncMock(side_effect=forbidden),
    )
    monkeypatch.setattr(
        retrieval_testing.service,
        "list_run_cases",
        AsyncMock(side_effect=forbidden),
    )
    monkeypatch.setattr(
        retrieval_testing.service,
        "cancel_run",
        AsyncMock(side_effect=forbidden),
    )
    monkeypatch.setattr(
        retrieval_testing.service,
        "test_run_output",
        lambda item: {"id": item.id, "status": item.status},
    )
    monkeypatch.setattr(
        retrieval_testing.service,
        "test_case_result_output",
        lambda item: {"id": item.id, "status": item.status},
    )

    app.dependency_overrides[retrieval_testing.get_current_user] = lambda: SimpleNamespace(
        id=other_id
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            responses = [
                await client.get(f"/api/v2/retrieval-test-runs/{run_id}"),
                await client.get(f"/api/v2/retrieval-test-runs/{run_id}/cases"),
                await client.post(f"/api/v2/retrieval-test-runs/{run_id}/cancel"),
            ]
        assert [item.json()["code"] for item in responses] == [40300, 40300, 40300]
        assert all(item.json()["data"] is None for item in responses)

        monkeypatch.setattr(
            retrieval_testing.service, "get_run", AsyncMock(return_value=run)
        )
        monkeypatch.setattr(
            retrieval_testing.service,
            "list_run_cases",
            AsyncMock(return_value=([result], 1)),
        )
        monkeypatch.setattr(
            retrieval_testing.service, "cancel_run", AsyncMock(return_value=run)
        )
        app.dependency_overrides[retrieval_testing.get_current_user] = (
            lambda: SimpleNamespace(id=owner_id)
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            read = await client.get(f"/api/v2/retrieval-test-runs/{run_id}")
            cases = await client.get(f"/api/v2/retrieval-test-runs/{run_id}/cases")
            cancel = await client.post(f"/api/v2/retrieval-test-runs/{run_id}/cancel")
        assert read.json()["data"] == {"id": str(run_id), "status": "running"}
        assert cases.json()["data"] == {
            "list": [{"id": result.id, "status": "running"}],
            "total": 1,
        }
        assert cancel.json()["data"] == {"id": str(run_id), "status": "running"}
    finally:
        app.dependency_overrides.pop(retrieval_testing.get_current_user, None)


def test_retrieval_testing_routes_are_registered_without_database():
    included = any(
        getattr(route, "original_router", None) is retrieval_testing.router
        for route in app.routes
    )
    assert included
    paths = {route.path for route in retrieval_testing.router.routes}
    expected = {
        "/knowledge/{kb_id}/retrieval-test-sets",
        "/retrieval-test-sets/{set_id}",
        "/retrieval-test-sets/{set_id}/cases",
        "/retrieval-test-cases/{case_id}",
        "/retrieval-test-cases/batch-status",
        "/retrieval-test-sets/{set_id}/runs",
        "/retrieval-test-runs/{run_id}",
        "/retrieval-test-runs/{run_id}/cases",
        "/retrieval-test-runs/{run_id}/cancel",
    }
    assert expected <= paths


def test_retrieval_worker_registers_async_run_task():
    from app.worker.app import WorkerSettings, run_retrieval_test_task

    assert run_retrieval_test_task in WorkerSettings.functions


def test_retrieval_run_create_preserves_invalid_ks_for_service_validation():
    body = retrieval_testing.RetrievalRunCreate(ks=[3, "5"])

    assert body.ks == [3, "5"]
