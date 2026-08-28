"""Document and chunk asset routes."""
import json
import uuid
from json import JSONDecodeError
from typing import Literal

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.response import ok
from app.config import settings
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.document import Document, ParseTask
from app.models.knowledge_base import KnowledgeBase
from app.providers.storage.factory import get_storage
from app.schemas.knowledge import ReembedRequest
from app.services import asset_service


router = APIRouter(tags=["assets"])

ALLOWED_EXT = {"pdf", "docx", "doc", "xlsx", "xls", "md", "txt", "markdown"}
MAX_SIZE = 50 * 1024 * 1024


class MetadataUpdate(BaseModel):
    metadata: dict


class BatchMetadata(BaseModel):
    ids: list[str] = Field(min_length=1)
    metadata: dict


class BatchStatus(BaseModel):
    ids: list[str] = Field(min_length=1)
    enabled: bool


def _metadata_filter(raw: str | None) -> dict | None:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except JSONDecodeError as exc:
        raise BizException(ErrorCode.PARAM_ERROR, "元数据筛选不是合法 JSON") from exc
    if not isinstance(value, dict):
        raise BizException(ErrorCode.PARAM_ERROR, "元数据筛选必须是对象")
    return value


def _validate_uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise BizException(ErrorCode.PARAM_ERROR, f"无效的{label}") from exc


@router.post("/documents/upload")
async def upload(
    file: UploadFile = File(...),
    kbId: str = Form(...),
    mode: str = Form("fast"),
    me=Depends(get_current_user),
):
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXT:
        raise BizException(ErrorCode.UNSUPPORTED_FILE, f"不支持的格式: {ext}")
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise BizException(ErrorCode.FILE_TOO_LARGE, "文件超过 50MB 限制")

    async with async_session() as session:
        kb = (
            await session.execute(
                select(KnowledgeBase).where(KnowledgeBase.id == kbId)
            )
        ).scalar_one_or_none()
        if not kb:
            raise BizException(ErrorCode.NOT_FOUND, "知识库不存在")
        if kb.user_id != me.id:
            raise BizException(ErrorCode.FORBIDDEN, "无权访问该知识库")
        document = Document(
            kb_id=kb.id,
            user_id=me.id,
            name=file.filename,
            ext=ext,
            size=len(data),
            mode=mode,
            status="pending",
            file_key="",
        )
        session.add(document)
        await session.flush()
        document.file_key = f"{kb.id}/{document.id}/{file.filename}"
        task = ParseTask(doc_id=document.id, kb_id=kbId, status="pending")
        session.add(task)
        await session.commit()
        await session.refresh(document)
        await session.refresh(task)
        doc_id, key, task_id = (
            str(document.id),
            document.file_key,
            str(task.id),
        )

    storage = get_storage()
    await storage.put(key, data)
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await pool.enqueue_job("parse_document_task", doc_id)
    return ok({"task_id": task_id, "doc_id": doc_id})


@router.get("/documents")
async def list_documents(
    kb_id: str,
    keyword: str | None = None,
    status: str | None = None,
    enabled: bool | None = None,
    document_metadata: str | None = None,
    sort: str = "created_desc",
    page: int = 1,
    page_size: int = 20,
    me=Depends(get_current_user),
):
    documents, total = await asset_service.list_documents(
        kb_id=kb_id,
        user_id=me.id,
        keyword=keyword,
        status=status,
        enabled=enabled,
        metadata_filter=_metadata_filter(document_metadata),
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return ok(
        {
            "list": [asset_service.asset_output(item, "document") for item in documents],
            "total": total,
        }
    )


@router.post("/documents/batch-metadata")
async def batch_document_metadata(
    body: BatchMetadata, me=Depends(get_current_user)
):
    updated = await asset_service.batch_update_metadata(
        body.ids, me.id, "document", body.metadata
    )
    return ok({"updated": updated})


@router.post("/documents/batch-status")
async def batch_document_status(body: BatchStatus, me=Depends(get_current_user)):
    updated = await asset_service.batch_update_status(
        body.ids, me.id, "document", body.enabled
    )
    return ok({"updated": updated})


@router.patch("/documents/{doc_id}/metadata")
async def update_document_metadata(
    doc_id: str, body: MetadataUpdate, me=Depends(get_current_user)
):
    document = await asset_service.update_document_metadata(
        doc_id, me.id, body.metadata
    )
    return ok(asset_service.asset_output(document, "document"))


@router.get("/documents/{doc_id}")
async def detail(doc_id: str, me=Depends(get_current_user)):
    async with async_session() as session:
        document = await asset_service._document_from(session, doc_id, me.id)
    return ok(asset_service.asset_output(document, "document"))


@router.delete("/documents/{doc_id}")
async def delete_doc(doc_id: str, me=Depends(get_current_user)):
    async with async_session() as session:
        document = await asset_service._document_from(session, doc_id, me.id)
        key = document.file_key
    await asset_service.delete_document(document)
    storage = get_storage()
    await storage.delete(key)
    return ok({"success": True})


@router.get("/chunks")
async def list_chunks(
    kb_id: str,
    keyword: str | None = None,
    document_id: str | None = None,
    vector_state: Literal["all", "vectorized", "pending"] = "all",
    enabled: bool | None = None,
    chunk_metadata: str | None = None,
    page: int = 1,
    page_size: int = 20,
    me=Depends(get_current_user),
):
    chunks, total = await asset_service.list_chunks(
        kb_id=kb_id,
        user_id=me.id,
        keyword=keyword,
        document_id=document_id,
        vector_state=vector_state,
        enabled=enabled,
        metadata_filter=_metadata_filter(chunk_metadata),
        page=page,
        page_size=page_size,
    )
    return ok(
        {
            "list": [asset_service.asset_output(item, "chunk") for item in chunks],
            "total": total,
        }
    )


@router.post("/chunks/reembed")
async def reembed_chunks(body: ReembedRequest, me=Depends(get_current_user)):
    kb_uuid = _validate_uuid(body.kb_id, "知识库 ID")
    for document_id in body.document_ids:
        _validate_uuid(document_id, "文档 ID")
    for chunk_id in body.chunk_ids:
        _validate_uuid(chunk_id, "分块 ID")

    async with async_session() as session:
        kb = (
            await session.execute(
                select(KnowledgeBase).where(
                    KnowledgeBase.id == kb_uuid,
                    KnowledgeBase.user_id == me.id,
                )
            )
        ).scalar_one_or_none()
    if not kb:
        raise BizException(ErrorCode.FORBIDDEN, "无权访问该知识库")

    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await pool.enqueue_job(
        "reembed_chunks_task",
        body.kb_id,
        body.document_ids,
        body.chunk_ids,
    )
    return ok({"queued": True})


@router.patch("/chunks/{chunk_id}/metadata")
async def update_chunk_metadata(
    chunk_id: str, body: MetadataUpdate, me=Depends(get_current_user)
):
    chunk = await asset_service.update_chunk_metadata(
        chunk_id, me.id, body.metadata
    )
    return ok(asset_service.asset_output(chunk, "chunk"))


@router.post("/chunks/batch-metadata")
async def batch_chunk_metadata(body: BatchMetadata, me=Depends(get_current_user)):
    updated = await asset_service.batch_update_metadata(
        body.ids, me.id, "chunk", body.metadata
    )
    return ok({"updated": updated})


@router.post("/chunks/batch-status")
async def batch_chunk_status(body: BatchStatus, me=Depends(get_current_user)):
    updated = await asset_service.batch_update_status(
        body.ids, me.id, "chunk", body.enabled
    )
    return ok({"updated": updated})
