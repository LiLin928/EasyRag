"""Saved retrieval test set and case routes."""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.response import ok
from app.schemas.retrieval_testing import (
    RetrievalTestCaseCreate,
    RetrievalTestCaseUpdate,
    RetrievalTestSetCreate,
    RetrievalTestSetUpdate,
    TestCaseBatchStatus,
)
from app.services import retrieval_test_service as service


router = APIRouter(tags=["retrieval-testing"])


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
