"""文档服务 V2 (Celery + Redis Streams 版)

展示如何将 PG Queue 迁移到 Celery + Streams
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.celery_app import celery_app
from app.core.redis_streams import publish_event
from app.models.document import Document, ParseTask
from app.schemas.document import DocumentOut

logger = logging.getLogger(__name__)


class DocumentServiceV2:
    """
    文档服务 V2
    
    使用 Celery 提交任务，Streams 推送事件
    """
    
    @staticmethod
    async def upload_document(
        session: AsyncSession,
        kb_id: int,
        filename: str,
        file_key: str,
        file_size: int,
        user_id: int,
    ) -> dict:
        """
        上传文档并提交解析任务
        
        V1: PGJobQueue.enqueue_task("parse_document", {...})
        V2: celery_app.send_task("parse_document", ...)
        """
        # 1. 创建文档记录
        doc = Document(
            kb_id=kb_id,
            name=filename,
            file_key=file_key,
            file_size=file_size,
            status="pending",
            created_by=user_id,
        )
        session.add(doc)
        await session.flush()  # 获取 doc_id
        
        # 2. 创建解析任务记录
        parse_task = ParseTask(
            doc_id=doc.id,
            status="pending",
            pct=0,
        )
        session.add(parse_task)
        await session.commit()
        
        # 3. 提交 Celery 任务 (V2 方式)
        # 旧: PGJobQueue.enqueue_task("parse_document", {"doc_id": doc.id})
        task = celery_app.send_task(
            "parse_document",
            args=[doc.id, file_key, kb_id],
            queue="parse",
            countdown=0,  # 立即执行
        )
        
        # 4. 可选：立即发布初始化事件
        await publish_event(
            f"parse:{doc.id}",
            "task_enqueued",
            {
                "doc_id": doc.id,
                "task_id": task.id,
                "kb_id": kb_id,
                "filename": filename,
                "pct": 0,
            }
        )
        
        logger.info(f"Document uploaded and parse task enqueued: doc_id={doc.id}, task_id={task.id}")
        
        return {
            "doc_id": doc.id,
            "task_id": task.id,
            "parse_task_id": parse_task.id,
            "status": "enqueued",
            "message": "Document uploaded, parsing in progress"
        }
    
    @staticmethod
    async def get_parse_progress(session: AsyncSession, doc_id: int) -> dict:
        """
        获取文档解析进度
        
        从数据库获取，前端也可以通过 SSE 实时订阅
        """
        from sqlalchemy import select
        
        result = await session.execute(
            select(ParseTask).where(ParseTask.doc_id == doc_id)
        )
        task = result.scalar_one_or_none()
        
        if not task:
            return {
                "doc_id": doc_id,
                "status": "not_found",
                "pct": 0
            }
        
        return {
            "doc_id": doc_id,
            "status": task.status,
            "pct": task.pct,
            "error": task.error,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None
        }


# 便捷函数
async def upload_and_parse(
    session: AsyncSession,
    kb_id: int,
    filename: str,
    file_key: str,
    file_size: int,
    user_id: int,
) -> dict:
    """便捷函数：上传并解析文档"""
    return await DocumentServiceV2.upload_document(
        session, kb_id, filename, file_key, file_size, user_id
    )
