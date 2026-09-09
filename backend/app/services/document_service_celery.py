"""文档服务 - Celery 集成版

在 asset_service.py 基础上添加 Celery 任务提交功能
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.redis_streams import publish_event
from app.exceptions import BizException, ErrorCode
from app.models.document import Document, ParseTask
from app.models.knowledge_base import KnowledgeBase
from app.providers.storage.factory import get_storage
import logging

logger = logging.getLogger(__name__)


class DocumentCeleryService:
    """使用 Celery 的文档服务"""
    
    # 扩展名白名单
    ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "xlsx", "xls", "md", "txt", "markdown"}
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    
    @staticmethod
    def _allowed_file(filename: str) -> bool:
        """检查文件扩展名是否允许"""
        return "." in filename and filename.rsplit(".", 1)[1].lower() in DocumentCeleryService.ALLOWED_EXTENSIONS
    
    @staticmethod
    async def upload_document(
        session: AsyncSession,
        kb_id: uuid.UUID,
        user_id: uuid.UUID,
        filename: str,
        file_content: bytes,
        file_size: int,
    ) -> dict:
        """
        上传文档并提交 Celery 解析任务
        
        完整流程:
        1. 校验文件类型和大小
        2. 保存到对象存储
        3. 创建数据库记录
        4. 提交 Celery 解析任务
        5. 发布初始化事件到 Redis Streams
        """
        # 1. 校验
        if not DocumentCeleryService._allowed_file(filename):
            raise BizException(
                ErrorCode.PARAM_ERROR,
                f"不支持的文件类型。允许: {DocumentCeleryService.ALLOWED_EXTENSIONS}"
            )
        
        if file_size > DocumentCeleryService.MAX_FILE_SIZE:
            raise BizException(
                ErrorCode.PARAM_ERROR,
                f"文件大小超过限制: {DocumentCeleryService.MAX_FILE_SIZE / 1024 / 1024}MB"
            )
        
        # 2. 验证知识库归属
        kb = await session.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        )
        kb = kb.scalar_one_or_none()
        if not kb:
            raise BizException(ErrorCode.NOT_FOUND, "知识库不存在")
        if kb.user_id != user_id:
            raise BizException(ErrorCode.FORBIDDEN, "无权访问该知识库")
        
        # 3. 创建文档记录
        doc = Document(
            kb_id=kb_id,
            name=filename,
            size=file_size,
            status="pending",
            user_id=user_id,
            element_count=0,
            chunk_count=0,
        )
        session.add(doc)
        await session.flush()  # 获取 doc.id
        
        # 4. 保存到对象存储
        file_key = f"{kb_id}/{doc.id}/{filename}"
        storage = get_storage()
        await storage.put(file_key, file_content)
        
        # 更新文档的 file_key
        doc.file_key = file_key
        
        # 5. 创建解析任务记录
        parse_task = ParseTask(
            doc_id=doc.id,
            status="pending",
            pct=0,
        )
        session.add(parse_task)
        await session.commit()
        
        # 6. 提交 Celery 任务
        celery_task = celery_app.send_task(
            "parse_document",
            args=[str(doc.id), file_key, str(kb_id)],
            queue="parse",
            countdown=0,
        )
        
        # 7. 发布初始化事件到 Redis Streams
        await publish_event(
            f"parse:{doc.id}",
            "task_enqueued",
            {
                "doc_id": str(doc.id),
                "task_id": celery_task.id,
                "kb_id": str(kb_id),
                "filename": filename,
                "file_size": file_size,
                "pct": 0,
                "status": "pending",
            }
        )
        
        logger.info(
            f"Document uploaded and parse task enqueued: "
            f"doc_id={doc.id}, task_id={celery_task.id}"
        )
        
        return {
            "code": 0,
            "message": "文档上传成功，正在解析",
            "data": {
                "doc_id": str(doc.id),
                "task_id": celery_task.id,
                "parse_task_id": str(parse_task.id),
                "kb_id": str(kb_id),
                "filename": filename,
                "status": "pending",
                "pct": 0,
            }
        }
    
    @staticmethod
    async def get_parse_progress(
        session: AsyncSession,
        doc_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> dict:
        """获取文档解析进度"""
        # 验证文档归属
        doc = await session.execute(
            select(Document).where(Document.id == doc_id)
        )
        doc = doc.scalar_one_or_none()
        
        if not doc:
            raise BizException(ErrorCode.NOT_FOUND, "文档不存在")
        
        # 验证知识库归属
        kb = await session.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == doc.kb_id)
        )
        kb = kb.scalar_one_or_none()
        if kb and kb.user_id != user_id:
            raise BizException(ErrorCode.FORBIDDEN, "无权访问该文档")
        
        # 获取解析任务
        parse_task = await session.execute(
            select(ParseTask).where(ParseTask.doc_id == doc_id)
        )
        parse_task = parse_task.scalar_one_or_none()
        
        if not parse_task:
            return {
                "code": 0,
                "data": {
                    "doc_id": str(doc_id),
                    "status": "unknown",
                    "pct": 0,
                    "error": None,
                }
            }
        
        return {
            "code": 0,
            "data": {
                "doc_id": str(doc_id),
                "status": parse_task.status,
                "pct": parse_task.pct,
                "error": parse_task.error,
                "updated_at": parse_task.updated_at.isoformat() if parse_task.updated_at else None,
            }
        }


# 便捷函数
async def upload_and_parse_document(
    session: AsyncSession,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    file_content: bytes,
    file_size: int,
) -> dict:
    """便捷函数：上传并解析文档"""
    return await DocumentCeleryService.upload_document(
        session, kb_id, user_id, filename, file_content, file_size
    )
