"""Per-KB retrieval settings routes."""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.response import ok
from app.schemas.knowledge import RetrievalSettingsUpdate
from app.services.retrieval_settings_service import (
    get_effective_settings,
    save_retrieval_settings,
)


router = APIRouter(
    prefix="/knowledge/{kb_id}/retrieval-settings",
    tags=["retrieval-settings"],
)


@router.get("")
async def get_settings(kb_id: str, me=Depends(get_current_user)):
    return ok(await get_effective_settings(kb_id, user_id=me.id))


@router.put("")
async def update_settings(
    kb_id: str,
    body: RetrievalSettingsUpdate,
    me=Depends(get_current_user),
):
    return ok(await save_retrieval_settings(
        kb_id=kb_id,
        user_id=me.id,
        embedding_model_id=body.embedding_model_id,
        rerank_model_id=body.rerank_model_id,
        retrieval_config=body.retrieval_config,
        update_embedding_model="embedding_model_id" in body.model_fields_set,
        update_rerank_model="rerank_model_id" in body.model_fields_set,
        update_retrieval_config="retrieval_config" in body.model_fields_set,
    ))
