"""文档解析 Celery 任务"""
import asyncio
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
import logging

from app.core.celery_app import celery_app
from app.core.redis_streams import publish_event

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def parse_document(self, doc_id: int, file_key: str, kb_id: int) -> dict:
    """
    文档解析任务
    
    完整流程: dispatcher → parser → tree_builder → chunker → embed
    
    Args:
        doc_id: 文档 ID
        file_key: 存储 key (格式: {kb_id}/{doc_id}/{filename})
        kb_id: 知识库 ID
        
    Returns:
        解析结果: {doc_id, status, chunks, vectors, ...}
    """
    stream_key = f"parse:{doc_id}"
    
    try:
        # 1. 发送开始事件
        _publish_sync(stream_key, "task_started", {
            "doc_id": doc_id,
            "kb_id": kb_id,
            "pct": 0,
            "step": "started"
        })
        
        # 2. 获取文件并解析
        _publish_sync(stream_key, "task_progress", {
            "doc_id": doc_id,
            "pct": 10,
            "step": "downloading"
        })
        
        # TODO: 调用 dispatcher → parser
        # from app.core.parser.dispatcher import parse
        # parsed_doc = parse(file_key)
        
        # 3. 构建文档树
        _publish_sync(stream_key, "task_progress", {
            "doc_id": doc_id,
            "pct": 30,
            "step": "building_tree"
        })
        
        # TODO: 调用 tree_builder
        # from app.core.parser.tree_builder import build_tree
        # tree = build_tree(doc_id, parsed_doc.elements)
        
        # 4. 分块
        _publish_sync(stream_key, "task_progress", {
            "doc_id": doc_id,
            "pct": 50,
            "step": "chunking"
        })
        
        # TODO: 调用 chunker
        # from app.core.parser.chunker import chunk
        # chunks = chunk(parsed_doc.elements)
        chunk_count = 42  # 示例
        
        # 5. Embedding
        _publish_sync(stream_key, "task_progress", {
            "doc_id": doc_id,
            "pct": 80,
            "step": "embedding",
            "chunk_count": chunk_count
        })
        
        # TODO: 调用 embed
        # from app.services.embedding_service import embed_chunks
        # vectors = embed_chunks(chunks)
        
        # 6. 完成
        result = {
            "doc_id": doc_id,
            "kb_id": kb_id,
            "status": "success",
            "chunks": chunk_count,
            "vectors": chunk_count,
        }
        
        _publish_sync(stream_key, "task_completed", {
            "doc_id": doc_id,
            "pct": 100,
            "result": result
        })
        
        logger.info(f"Parse task completed: doc_id={doc_id}")
        return result
        
    except Exception as exc:
        logger.error(f"Parse task failed: doc_id={doc_id}, error={exc}")
        
        # 发布失败事件
        _publish_sync(stream_key, "task_failed", {
            "doc_id": doc_id,
            "error": str(exc),
            "retry_count": self.request.retries
        })
        
        # 重试
        if self.request.retries < self.max_retries:
            _publish_sync(stream_key, "task_retrying", {
                "doc_id": doc_id,
                "retry_count": self.request.retries + 1,
                "max_retries": self.max_retries
            })
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
        
        # 最终失败
        raise


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
        # 创建新的事件循环来运行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(publish_event(stream, event_type, payload))
        loop.close()
    except Exception as e:
        logger.warning(f"Failed to publish event: {e}")
