"""Document and chunk asset routes."""
import json
import uuid
from json import JSONDecodeError
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.response import ok

from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.document import Document, ParseTask
from app.models.knowledge_base import KnowledgeBase
from app.providers.storage.factory import get_storage
from app.schemas.knowledge import ReembedRequest
from app.services import asset_service
from app.core.celery_app import celery_app


router = APIRouter(tags=["assets"])

# 支持的文件格式
# 注意：不支持 Word 97-2003 格式 (.doc)
# 原因：python-docx 仅支持 .docx (ZIP 格式)
ALLOWED_EXT = {"pdf", "docx", "xlsx", "xls", "md", "txt", "markdown"}
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
    """上传文档到知识库

    支持的文件格式：
    - PDF (.pdf)
    - Word 2007+ (.docx) - 注意：不支持 Word 97-2003 (.doc)
    - Excel (.xlsx, .xls)
    - Markdown (.md, .markdown)
    - 纯文本 (.txt)

    Args:
        file: 上传的文件
        kbId: 知识库 ID
        mode: 解析模式（fast/standard）

    Returns:
        {"task_id": "解析任务ID", "doc_id": "文档ID"}
    """
    ext = file.filename.rsplit(".", 1)[-1].lower()

    # 特殊提示 .doc 文件
    if ext == "doc":
        raise BizException(
            ErrorCode.UNSUPPORTED_FILE,
            "不支持 Word 97-2003 格式（.doc），请转换为 .docx 格式后再上传"
        )

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
            name=file.filename,  # 保存原始文件名用于显示
            ext=ext,
            size=len(data),
            mode=mode,
            status="pending",
            file_key="",
        )
        session.add(document)
        await session.flush()
        # 使用文档 ID 作为文件名，避免中文编码问题
        document.file_key = f"{kb.id}/{document.id}/{document.id}.{ext}"
        task = ParseTask(doc_id=document.id, kb_id=str(kb.id), status="pending")
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

    # Submit to Celery queue
    try:
        celery_app.send_task(
            "app.worker.tasks.parse_tasks.parse_document",  # 完整的任务路径
            args=[doc_id, key, str(kb.id)],
            queue="parse",
            task_id=task_id,
        )
    except Exception as e:
        # Celery 任务提交失败不影响文档上传成功
        import logging
        logging.error(f"Failed to submit Celery task: {e}")

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
    # 先获取文件键
    async with async_session() as session:
        document = await asset_service._document_from(session, doc_id, me.id)
        key = document.file_key

    # 删除数据库记录
    await asset_service.delete_document(document)

    # 删除存储文件
    storage = get_storage()
    try:
        await storage.delete(key)
    except Exception as e:
        # 存储删除失败不影响数据库记录删除
        import logging
        logging.error(f"Failed to delete file from storage: {e}")

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


@router.get("/child-chunks")
async def list_child_chunks(
    kb_id: str,
    keyword: str | None = None,
    document_id: str | None = None,
    vector_state: Literal["all", "vectorized", "pending"] = "all",
    enabled: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    me=Depends(get_current_user),
):
    """列出子分段（父子分段模式下的检索单元）。

    Args:
        kb_id: 知识库 ID。
        keyword: 内容关键词。
        document_id: 按文档过滤。
        vector_state: all/vectorized/pending。
        enabled: 启用状态过滤。
        page/page_size: 分页。
    """
    items, total = await asset_service.list_child_chunks(
        kb_id=kb_id,
        user_id=me.id,
        keyword=keyword,
        document_id=document_id,
        vector_state=vector_state,
        enabled=enabled,
        page=page,
        page_size=page_size,
    )
    return ok(
        {
            "list": [asset_service.child_chunk_output(item) for item in items],
            "total": total,
        }
    )


@router.patch("/child-chunks/{child_id}/metadata")
async def update_child_chunk_metadata(
    child_id: str, body: MetadataUpdate, me=Depends(get_current_user)
):
    """更新单个子分段的元数据（父子分段模式）。"""
    child = await asset_service.update_child_chunk_metadata(
        child_id, me.id, body.metadata
    )
    return ok(asset_service.child_chunk_output(child))


@router.post("/child-chunks/batch-metadata")
async def batch_child_chunk_metadata(
    body: BatchMetadata, me=Depends(get_current_user)
):
    """批量更新子分段元数据（父子分段模式）。"""
    updated = await asset_service.batch_update_metadata(
        body.ids, me.id, "child_chunk", body.metadata
    )
    return ok({"updated": updated})


@router.post("/child-chunks/batch-status")
async def batch_child_chunk_status(
    body: BatchStatus, me=Depends(get_current_user)
):
    """批量启用/停用子分段（父子分段模式）。"""
    updated = await asset_service.batch_update_status(
        body.ids, me.id, "child_chunk", body.enabled
    )
    return ok({"updated": updated})


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

    # 提交重建索引任务到 Celery 队列
    try:
        from app.core.celery_app import celery_app
        task = celery_app.send_task(
            "app.worker.tasks.parse_tasks.reembed_chunks",
            args=[str(kb_uuid), body.document_ids, body.chunk_ids],
            queue="parse",
        )
        return ok({"queued": True, "task_id": task.id})
    except Exception as e:
        import logging
        logging.error(f"Failed to submit reembed task: {e}")
        raise BizException(ErrorCode.INTERNAL_ERROR, "提交重建索引任务失败")


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


