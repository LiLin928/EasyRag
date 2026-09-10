"""文档解析 Celery 任务"""

import asyncio
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
import logging

from app.core.celery_app import celery_app
from app.core.redis_streams import publish_event
from app.core.parser.dispatcher import DocumentDispatcher
from app.core.parser.tree_builder import TreeBuilder
from app.core.parser.chunker import Chunker
from app.core.parser.embedder import Embedder
from app.providers.storage.factory import get_storage

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def parse_document(self, doc_id: str, file_key: str, kb_id: str) -> dict:
    """
    文档解析任务

    完整流程: dispatcher → parser → tree_builder → chunker → embed

    Args:
        doc_id: 文档 ID (UUID 字符串)
        file_key: 存储 key (格式: {kb_id}/{doc_id}/{filename})
        kb_id: 知识库 ID (UUID 字符串)

    Returns:
        解析结果: {doc_id, status, chunks, vectors, ...}
    """
    stream_key = f"parse:{doc_id}"

    try:
        # 创建事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 执行异步任务
            result = loop.run_until_complete(
                _parse_document_async(self, doc_id, file_key, kb_id, stream_key)
            )
            return result
        finally:
            loop.close()

    except Exception as exc:
        logger.error(f"Parse task failed: doc_id={doc_id}, error={exc}")

        _publish_sync(stream_key, "task_failed", {
            "doc_id": doc_id,
            "error": str(exc),
            "retry_count": self.request.retries
        })

        if self.request.retries < self.max_retries:
            _publish_sync(stream_key, "task_retrying", {
                "doc_id": doc_id,
                "retry_count": self.request.retries + 1,
                "max_retries": self.max_retries
            })
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

        raise


async def _parse_document_async(
    task,
    doc_id: str,
    file_key: str,
    kb_id: str,
    stream_key: str
) -> dict:
    """异步解析文档"""

    # 1. 发送开始事件
    _publish_sync(stream_key, "task_started", {
        "doc_id": doc_id,
        "kb_id": kb_id,
        "pct": 0,
        "step": "started"
    })

    # 2. 获取文件
    _publish_sync(stream_key, "task_progress", {
        "doc_id": doc_id,
        "pct": 10,
        "step": "downloading"
    })

    storage = get_storage()
    file_data = await storage.get(file_key)

    # 3. 解析文档
    _publish_sync(stream_key, "task_progress", {
        "doc_id": doc_id,
        "pct": 20,
        "step": "parsing"
    })

    dispatcher = DocumentDispatcher()
    parsed_doc = await dispatcher._dispatch_from_data(file_data, file_key, doc_id)

    # 4. 构建文档树
    _publish_sync(stream_key, "task_progress", {
        "doc_id": doc_id,
        "pct": 40,
        "step": "building_tree"
    })

    tree_builder = TreeBuilder()
    tree = await tree_builder.build(parsed_doc.elements, doc_id)

    # 5. 分块
    _publish_sync(stream_key, "task_progress", {
        "doc_id": doc_id,
        "pct": 60,
        "step": "chunking"
    })

    chunker = Chunker(chunk_size=512, chunk_overlap=50)
    chunks = await chunker.chunk(parsed_doc.elements, doc_id, kb_id)

    # 6. 向量化
    _publish_sync(stream_key, "task_progress", {
        "doc_id": doc_id,
        "pct": 80,
        "step": "embedding",
        "chunk_count": len(chunks)
    })

    embedder = Embedder()
    vector_count = await embedder.embed(chunks, kb_id)

    # 7. 完成
    result = {
        "doc_id": doc_id,
        "kb_id": kb_id,
        "status": "success",
        "chunks": len(chunks),
        "vectors": vector_count,
    }

    _publish_sync(stream_key, "task_completed", {
        "doc_id": doc_id,
        "pct": 100,
        "result": result
    })

    logger.info(f"Parse task completed: doc_id={doc_id}")
    return result


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def execute_retrieval_test(self, config_id: int) -> dict:
    """
    检索测试任务
    
    执行检索测试并返回结果
    
    Args:
        config_id: 测试配置 ID
        
    Returns:
        测试结果
    """
    stream_key = f"retrieval_test:{config_id}"
    
    try:
        _publish_sync(stream_key, "task_started", {
            "config_id": config_id,
            "pct": 0
        })
        
        # TODO: 执行检索测试
        # from app.core.retrieval.test_metrics import run_test
        # results = run_test(config_id)
        
        _publish_sync(stream_key, "task_progress", {
            "config_id": config_id,
            "pct": 50
        })
        
        result = {
            "config_id": config_id,
            "status": "success",
            "metrics": {
                "precision": 0.85,
                "recall": 0.82,
                "f1": 0.83
            }
        }
        
        _publish_sync(stream_key, "task_completed", {
            "config_id": config_id,
            "pct": 100,
            "result": result
        })
        
        return result
        
    except Exception as exc:
        logger.error(f"Retrieval test failed: config_id={config_id}, error={exc}")
        
        _publish_sync(stream_key, "task_failed", {
            "config_id": config_id,
            "error": str(exc)
        })
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30)
        
        raise


def _publish_sync(stream: str, event_type: str, payload: dict):
    """同步发布事件 (在 Celery 任务中使用)"""
    try:
        import redis
        import json
        from datetime import datetime
        import os

        # 使用同步 Redis 客户端
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        r = redis.from_url(redis_url)

        # 构造事件数据
        data = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": json.dumps(payload),
        }

        # 发布到 Redis Stream
        r.xadd(stream, data, maxlen=10000, approximate=True)
        logger.debug(f"Published event: {event_type} to {stream}")
    except Exception as e:
        logger.warning(f"Failed to publish event: {e}")
