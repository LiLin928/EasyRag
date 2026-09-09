"""Metadata schema routes."""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.knowledge_base import KnowledgeBase
from app.models.metadata import KbMetadataField
from app.schemas.knowledge import (
    MetadataFieldCreate,
    MetadataFieldOut,
    MetadataFieldReorder,
    MetadataFieldUpdate,
)
from app.services import metadata_service as ms


router = APIRouter(prefix="/knowledge/{kb_id}/metadata-fields", tags=["metadata"])


def _uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise BizException(ErrorCode.PARAM_ERROR, f"无效的{label}")


def _out(field: KbMetadataField) -> dict:
    return MetadataFieldOut(
        id=str(field.id),
        kb_id=str(field.kb_id),
        key=field.key,
        name=field.name,
        scope=field.scope,
        data_type=field.data_type,
        options=field.options or [],
        default_value=field.default_value,
        required=bool(field.required),
        filterable=bool(field.filterable),
        retrieval_filterable=bool(field.retrieval_filterable),
        visible=bool(field.visible),
        built_in=bool(field.built_in),
        mapped_field=field.mapped_field,
        sort_order=field.sort_order,
    ).model_dump()


@router.get("")
async def list_fields(kb_id: str, scope: str | None = None, me=Depends(get_current_user)):
    """List metadata fields, seeding built-ins idempotently."""
    await ms.ensure_default_fields(kb_id, user_id=me.id)
    fields = await ms.list_fields(kb_id, me.id, scope)
    return ok([_out(field) for field in fields])


@router.post("", status_code=201)
async def create_field(kb_id: str, body: MetadataFieldCreate, me=Depends(get_current_user)):
    """Create a custom metadata field."""
    field = await ms.create_field(
        kb_id=kb_id,
        user_id=me.id,
        key=body.key,
        name=body.name,
        scope=body.scope,
        data_type=body.data_type,
        options=body.options,
        default_value=body.default_value,
        required=body.required,
        filterable=body.filterable,
        retrieval_filterable=body.retrieval_filterable,
        visible=body.visible,
        sort_order=body.sort_order,
    )
    return ok(_out(field))


@router.put("/reorder")
async def reorder_fields(kb_id: str, body: MetadataFieldReorder, me=Depends(get_current_user)):
    """Reorder fields within one owned knowledge base."""
    ids = body.ids
    if len(ids) != len(set(ids)):
        raise BizException(ErrorCode.PARAM_ERROR, "字段排序 ID 不能重复")
    kb_uuid = _uuid(kb_id, "知识库 ID")
    field_ids = [_uuid(field_id, "字段 ID") for field_id in ids]
    async with async_session() as session:
        query = (
            select(KbMetadataField)
            .join(KnowledgeBase, KbMetadataField.kb_id == KnowledgeBase.id)
            .where(
                KnowledgeBase.id == kb_uuid,
                KnowledgeBase.user_id == me.id,
                KbMetadataField.id.in_(field_ids),
            )
        )
        fields = (await session.execute(query)).scalars().all()
        by_id = {str(field.id): field for field in fields}
        if len(by_id) != len(ids):
            raise BizException(ErrorCode.NOT_FOUND, "部分排序字段不存在")
        for sort_order, field_id in enumerate(ids):
            by_id[field_id].sort_order = sort_order
        await session.commit()
    return ok({"success": True})


@router.put("/{field_id}")
async def update_field(
    kb_id: str,
    field_id: str,
    body: MetadataFieldUpdate,
    me=Depends(get_current_user),
):
    """Update allowed metadata-field settings."""
    field = await ms.update_field(
        field_id,
        me.id,
        kb_id=kb_id,
        **body.model_dump(exclude_unset=True),
    )
    return ok(_out(field))


@router.delete("/{field_id}")
async def delete_field(
    kb_id: str,
    field_id: str,
    force: bool = False,
    me=Depends(get_current_user),
):
    """Delete a custom field after checking stored-value impact."""
    impact = await ms.delete_field(field_id, me.id, kb_id=kb_id, force=force)
    return ok(impact)
