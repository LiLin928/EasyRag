"""Retrieval debug API."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.api.response import ok
from app.core.retrieval.metadata_filter import (
    MetadataFilter,
    build_sql_predicates,
)
from app.core.retrieval.pipeline import RetrievalPipeline
from app.services import metadata_service
from app.services.retrieval_settings_service import (
    SYSTEM_DEFAULTS,
    get_effective_settings,
)


router = APIRouter(tags=["retrieval"])


class SearchReq(BaseModel):
    kb_ids: list[str] = []
    document_ids: list[str] = []
    question: str
    top_k: int | None = None
    override_config: dict = {}
    document_metadata: dict = {}
    chunk_metadata: dict = {}


def _system_effective() -> dict:
    values = {
        key: {"value": value, "source": "system_default"}
        for key, value in SYSTEM_DEFAULTS.items()
    }
    return {"values": values, "resolved": dict(SYSTEM_DEFAULTS)}


@router.post("/search")
async def search_api(req: SearchReq, me=Depends(get_current_user)):
    """Run a metadata-aware retrieval test without incrementing recall counts."""
    if req.kb_ids:
        await metadata_service.require_owned_kbs(req.kb_ids, me.id)

    metadata_filter = None
    if req.kb_ids and (req.document_metadata or req.chunk_metadata):
        metadata_filter = MetadataFilter(
            document=req.document_metadata,
            chunk=req.chunk_metadata,
        )
        for kb_id in req.kb_ids:
            document_fields = await metadata_service.list_fields(
                kb_id, me.id, "document"
            )
            chunk_fields = await metadata_service.list_fields(kb_id, me.id, "chunk")
            build_sql_predicates(metadata_filter, document_fields, chunk_fields)

    if len(req.kb_ids) == 1:
        effective = await get_effective_settings(
            req.kb_ids[0],
            user_id=me.id,
            override=req.override_config or None,
        )
        embedding_model = effective.get("embedding_model")
        rerank_model = effective.get("rerank_model")
    else:
        effective = _system_effective()
        if req.override_config:
            # Keep the debug endpoint's explicit override behavior deterministic.
            from app.services.retrieval_settings_service import (
                validate_retrieval_config,
            )

            supplied = validate_retrieval_config(req.override_config, partial=True)
            effective["resolved"].update(supplied)
            for key, value in supplied.items():
                effective["values"][key] = {"value": value, "source": "override"}
        embedding_model = None
        rerank_model = None

    pipeline = RetrievalPipeline(
        settings=effective,
        embedding_model=embedding_model,
        rerank_model=rerank_model,
    )
    result = await pipeline.search(
        req.question,
        kb_ids=req.kb_ids,
        doc_ids=req.document_ids or None,
        scope=None,
        metadata_filter=metadata_filter,
        top_k=req.top_k,
        enable_nav=None,
        count_recall=False,
    )
    return ok({
        "results": result.chunks,
        "rerank_triggered": result.rerank_triggered,
        "rerank_skipped_reason": result.rerank_skipped_reason,
        "mode": result.mode,
        "nav_info": result.nav_info,
    })
