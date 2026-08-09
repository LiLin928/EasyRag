"""documents 路由：上传(multipart)+列表+详情+删除。"""
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import delete, select

from app.api.deps import get_current_user
from app.api.response import ok
from app.config import settings
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.document import Document, ParseTask
from app.models.knowledge_base import KnowledgeBase
from app.providers.storage.factory import get_storage
from app.schemas.document import DocOut

router = APIRouter(tags=["documents"])

ALLOWED_EXT = {"pdf", "docx", "doc", "xlsx", "xls", "md", "txt", "markdown"}
MAX_SIZE = 50 * 1024 * 1024


def _out(d: Document) -> dict:
    """构造文档响应字典。"""
    return DocOut(id=str(d.id), kb_id=str(d.kb_id), name=d.name, ext=d.ext, size=d.size,
                  status=d.status, pct=d.pct, mode=d.mode, pages=d.pages,
                  element_count=d.element_count,
                  created_at=d.created_at.isoformat() if d.created_at else "").model_dump()


@router.post("/documents/upload")
async def upload(file: UploadFile = File(...), kbId: str = Form(...), mode: str = Form("fast"),
                 me=Depends(get_current_user)):
    """上传文档：校验格式/大小 → 建 Document+ParseTask → 存文件 → 入队解析任务。"""
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXT:
        raise BizException(ErrorCode.UNSUPPORTED_FILE, f"不支持的格式: {ext}")
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise BizException(ErrorCode.FILE_TOO_LARGE, "文件超过 50MB 限制")

    async with async_session() as s:
        kb = (await s.execute(select(KnowledgeBase).where(KnowledgeBase.id == kbId))).scalar_one_or_none()
        if not kb:
            raise BizException(ErrorCode.NOT_FOUND, "知识库不存在")
        doc = Document(kb_id=kbId, user_id=me.id, name=file.filename, ext=ext, size=len(data),
                       mode=mode, status="pending", file_key="")
        s.add(doc)
        await s.flush()
        doc.file_key = f"{kbId}/{doc.id}/{file.filename}"
        task = ParseTask(doc_id=doc.id, kb_id=kbId, status="pending")
        s.add(task)
        await s.commit()
        await s.refresh(doc)
        await s.refresh(task)
        doc_id, key, task_id = str(doc.id), doc.file_key, str(task.id)

    storage = get_storage()
    await storage.put(key, data)

    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await pool.enqueue_job("parse_document_task", doc_id)

    return ok({"task_id": task_id, "doc_id": doc_id})


@router.get("/documents")
async def list_docs(kb_id: str = Query(...), me=Depends(get_current_user)):
    """列出知识库下的文档，按创建时间倒序。"""
    async with async_session() as s:
        rows = (await s.execute(select(Document).where(Document.kb_id == kb_id)
                                .order_by(Document.created_at.desc()))).scalars().all()
    return ok({"list": [_out(r) for r in rows], "total": len(rows)})


@router.get("/documents/{doc_id}")
async def detail(doc_id: str, me=Depends(get_current_user)):
    """获取文档详情。"""
    async with async_session() as s:
        d = (await s.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
    if not d:
        raise BizException(ErrorCode.NOT_FOUND, "文档不存在")
    return ok(_out(d))


@router.delete("/documents/{doc_id}")
async def delete_doc(doc_id: str, me=Depends(get_current_user)):
    """删除文档（含存储文件）。"""
    async with async_session() as s:
        d = (await s.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
        if not d:
            raise BizException(ErrorCode.NOT_FOUND, "文档不存在")
        key = d.file_key
        await s.execute(delete(Document).where(Document.id == doc_id))
        await s.commit()
    storage = get_storage()
    await storage.delete(key)
    return ok({"success": True})
