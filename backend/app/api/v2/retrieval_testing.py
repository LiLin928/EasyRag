"""Saved retrieval test set and case routes."""
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.api.response import ok
from app.config import settings
from app.schemas.retrieval_testing import (
    RetrievalTestCaseCreate,
    RetrievalTestCaseUpdate,
    RetrievalTestSetCreate,
    RetrievalTestSetUpdate,
    TestCaseBatchStatus,
)
from app.services import retrieval_test_service as service


router = APIRouter(tags=["retrieval-testing"])


class RetrievalRunCreate(BaseModel):
    case_ids: list[str] = []
    # Keep raw values so invalid Ks receive the unified business error envelope.
    ks: list[Any] = [3, 5, 10]
    override_config: dict = {}
    document_metadata: dict = {}
    chunk_metadata: dict = {}


@router.get("/knowledge/{kb_id}/retrieval-test-sets")
async def list_test_sets(
    kb_id: str, include_archived: bool = False, me=Depends(get_current_user)
):
    test_sets, total = await service.list_test_sets(
        kb_id, me.id, include_archived=include_archived
    )
    return ok(
        {
            "list": [service.test_set_output(item) for item in test_sets],
            "total": total,
        }
    )


@router.post("/knowledge/{kb_id}/retrieval-test-sets")
async def create_test_set(
    kb_id: str, body: RetrievalTestSetCreate, me=Depends(get_current_user)
):
    test_set = await service.create_test_set(
        kb_id, me.id, body.name, body.description
    )
    return ok(service.test_set_output(test_set))


@router.get("/retrieval-test-sets/{set_id}")
async def get_test_set(set_id: str, me=Depends(get_current_user)):
    test_set = await service.get_test_set(set_id, me.id)
    return ok(service.test_set_output(test_set))


@router.put("/retrieval-test-sets/{set_id}")
async def update_test_set(
    set_id: str, body: RetrievalTestSetUpdate, me=Depends(get_current_user)
):
    test_set = await service.update_test_set(
        set_id, me.id, **body.model_dump(exclude_unset=True)
    )
    return ok(service.test_set_output(test_set))


@router.delete("/retrieval-test-sets/{set_id}")
async def delete_test_set(set_id: str, me=Depends(get_current_user)):
    await service.delete_test_set(set_id, me.id)
    return ok({"success": True})


@router.get("/retrieval-test-sets/{set_id}/cases")
async def list_cases(
    set_id: str, enabled: bool | None = None, me=Depends(get_current_user)
):
    cases, total = await service.list_cases(set_id, me.id, enabled=enabled)
    return ok(
        {"list": [service.test_case_output(item) for item in cases], "total": total}
    )


@router.post("/retrieval-test-sets/{set_id}/cases")
async def create_case(
    set_id: str, body: RetrievalTestCaseCreate, me=Depends(get_current_user)
):
    case = await service.create_case(set_id, me.id, **body.model_dump())
    return ok(service.test_case_output(case))


@router.post("/retrieval-test-cases/batch-status")
async def batch_case_status(
    body: TestCaseBatchStatus, me=Depends(get_current_user)
):
    updated = await service.batch_case_status(body.ids, me.id, body.enabled)
    return ok({"updated": updated})


@router.put("/retrieval-test-cases/{case_id}")
async def update_case(
    case_id: str, body: RetrievalTestCaseUpdate, me=Depends(get_current_user)
):
    case = await service.update_case(
        case_id, me.id, **body.model_dump(exclude_unset=True)
    )
    return ok(service.test_case_output(case))


@router.delete("/retrieval-test-cases/{case_id}")
async def delete_case(case_id: str, me=Depends(get_current_user)):
    await service.delete_case(case_id, me.id)
    return ok({"success": True})


@router.get("/retrieval-test-sets/{set_id}/runs")
async def list_runs(set_id: str, me=Depends(get_current_user)):
    runs, total = await service.list_runs(set_id, me.id)
    return ok(
        {"list": [service.test_run_output(item) for item in runs], "total": total}
    )


@router.post("/retrieval-test-sets/{set_id}/runs")
async def start_run(set_id: str, body: RetrievalRunCreate, me=Depends(get_current_user)):
    run = await service.start_run(
        test_set_id=set_id,
        user_id=me.id,
        case_ids=body.case_ids,
        ks=body.ks,
        override_config=body.override_config,
        document_metadata=body.document_metadata,
        chunk_metadata=body.chunk_metadata,
    )
    if getattr(run, "_newly_created", False):
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await pool.enqueue_job("run_retrieval_test_task", str(run.id))
    return ok(service.test_run_output(run))


@router.get("/retrieval-test-runs/{run_id}")
async def get_run(run_id: str, me=Depends(get_current_user)):
    run = await service.get_run(run_id, me.id)
    return ok(service.test_run_output(run))


@router.get("/retrieval-test-runs/{run_id}/cases")
async def list_run_cases(run_id: str, me=Depends(get_current_user)):
    results, total = await service.list_run_cases(run_id, me.id)
    return ok(
        {
            "list": [service.test_case_result_output(item) for item in results],
            "total": total,
        }
    )


@router.post("/retrieval-test-runs/{run_id}/cancel")
async def cancel_run(run_id: str, me=Depends(get_current_user)):
    run = await service.cancel_run(run_id, me.id)
    return ok(service.test_run_output(run))
