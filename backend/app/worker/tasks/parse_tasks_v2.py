"""文档解析 Celery 任务 - 数据库集成版"""
import asyncio
import json
from datetime import datetime
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError, Retry
import logging

from app.core.celery_app import celery_app
from app.core.redis_streams import publish_event
from app.db.session import async_session
from app.models.document import Document, ParseTask
from sqlalchemy import select, update

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, time_limit=600)
def parse_document(self, doc_id_str: str, file_key: str, kb_id_str: str) -> dict:
    """
    文档解析任务（数据库集成版）
    
    完整流程: 下载 -> 解析 -> 构建树 -> 分块 -> Embedding
    每步更新数据库和发布 Streams 事件
    """
    import uuid
    doc_id = uuid.UUID(doc_id_str)
    kb_id = uuid.UUID(kb_id_str)
    stream_key = f"parse:{doc_id}"
    
    async def _execute():
        async with async_session() as session:
            try:
                # 1. 更新任务状态为运行中
                await _update_parse_task(session, doc_id, "running", 5, None)
                await session.commit()
                
                # 2. 发送开始事件
                await publish_event(stream_key, "task_started", {
                    "doc_id": str(doc_id),
                    "kb_id": str(kb_id),
                    "file_key": file_key,
                    "pct": 5,
                    "step": "started"
                })
                
                # 3. 获取文件并解析
                await _update_parse_task(session, doc_id, "running", 15, None)
                await session.commit()
                
                await publish_event(stream_key, "task_progress", {
                    "doc_id": str(doc_id),
                    "pct": 15,
                    "step": "downloading"
                })
                
                # TODO: 实际文件下载和解码
                # from app.providers.storage.factory import get_storage
                # storage = get_storage()
                # file_content = await storage.get(file_key)
                
                # 4. 解析文档
                await _update_parse_task(session, doc_id, "running", 30, None)
                await session.commit()
                
                await publish_event(stream_key, "task_progress", {
                    "doc_id": str(doc_id),
                    "pct": 30,
                    "step": "parsing"
                })
                
                # TODO: 调用 dispatcher
                # from app.core.parser.dispatcher import parse
                # parsed_doc = await parse(file_key)
                element_count = 42  # 示例
                
                # 5. 构建文档树
                await _update_parse_task(session, doc_id, "running", 45, None)
                await session.commit()
                
                await publish_event(stream_key, "task_progress", {
                    "doc_id": str(doc_id),
                    "pct": 45,
                    "step": "building_tree"
                })
                
                # TODO: 调用 tree_builder
                # from app.core.parser.tree_builder import build_tree
                # tree = await build_tree(doc_id, parsed_doc.elements)
                
                # 6. 分块
                await _update_parse_task(session, doc_id, "running", 60, None)
                await session.commit()
                
                await publish_event(stream_key, "task_progress", {
                    "doc_id": str(doc_id),
                    "pct": 60,
                    "step": "chunking",
                    "element_count": element_count
                })
                
                # TODO: 调用 chunker
                # from app.core.parser.chunker import chunk
                # chunks = await chunk(parsed_doc.elements)
                chunk_count = 15  # 示例
                
                # 7. Embedding
                await _update_parse_task(session, doc_id, "running", 85, None)
                await session.commit()
                
                await publish_event(stream_key, "task_progress", {
                    "doc_id": str(doc_id),
                    "pct": 85,
                    "step": "embedding",
                    "chunk_count": chunk_count
                })
                
                # TODO: 调用 embedding 服务
                # from app.services.embedding_service import embed_chunks
                # await embed_chunks(chunks)
                
                # 8. 更新文档完成状态
                await session.execute(
                    update(Document)
                    .where(Document.id == doc_id)
                    .values(
                        status="completed",
                        element_count=element_count,
                        chunk_count=chunk_count,
                        updated_at=datetime.utcnow()
                    )
                )
                await _update_parse_task(session, doc_id, "completed", 100, None)
                await session.commit()
                
                # 9. 发送完成事件
                result = {
                    "doc_id": str(doc_id),
                    "kb_id": str(kb_id),
                    "status": "completed",
                    "element_count": element_count,
                    "chunk_count": chunk_count,
                }
                
                await publish_event(stream_key, "task_completed", {
                    "doc_id": str(doc_id),
                    "pct": 100,
                    "result": result
                })
                
                logger.info(f"Parse task completed: doc_id={doc_id}")
                return result
                
            except Exception as exc:
                logger.error(f"Parse task failed: doc_id={doc_id}, error={exc}")
                
                # 更新失败状态
                await _update_parse_task(session, doc_id, "failed", 0, str(exc))
                await session.execute(
                    update(Document)
                    .where(Document.id == doc_id)
                    .values(status="failed")
                )
                await session.commit()
                
                # 发布失败事件
                await publish_event(stream_key, "task_failed", {
                    "doc_id": str(doc_id),
                    "error": str(exc),
                    "retry_count": self.request.retries
                })
                
                raise
    
    # 运行异步函数
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_execute())
        loop.close()
        return result
    except Exception as exc:
        # 重试逻辑
        if self.request.retries < self.max_retries:
            _publish_sync(stream_key, "task_retrying", {
                "doc_id": str(doc_id),
                "retry_count": self.request.retries + 1,
                "max_retries": self.max_retries
            })
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
        raise


async def _update_parse_task(session, doc_id, status, pct, error):
    """更新解析任务状态"""
    await session.execute(
        update(ParseTask)
        .where(ParseTask.doc_id == doc_id)
        .values(
            status=status,
            pct=pct,
            error=error,
            updated_at=datetime.utcnow()
        )
    )


def _publish_sync(stream: str, event_type: str, payload: dict):
    """同步发布事件"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(publish_event(stream, event_type, payload))
        loop.close()
    except Exception as e:
        logger.warning(f"Failed to publish event: {e}")
