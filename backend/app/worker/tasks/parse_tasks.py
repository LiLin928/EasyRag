"""文档解析 Celery 任务"""

import asyncio
import sys
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
import logging

from sqlalchemy import select  # 添加 select 导入

from app.core.celery_app import celery_app
from app.core.redis_streams import publish_event
from app.core.parser.dispatcher import DocumentDispatcher
from app.core.parser.tree_builder import TreeBuilder
from app.core.parser.chunker import Chunker
from app.core.parser.embedder import Embedder
from app.providers.storage.factory import get_storage
from app.db.session import async_session  # 添加异步 session 导入

logger = logging.getLogger(__name__)

# Celery Worker 持久事件循环
_event_loop = None


def _get_event_loop():
    """获取或创建持久事件循环

    Windows 环境必须使用 WindowsSelectorEventLoopPolicy，
    否则 asyncpg 会报错：another operation is in progress
    """
    global _event_loop
    if _event_loop is None or _event_loop.is_closed():
        # Windows 环境：设置正确的事件循环策略
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        _event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_event_loop)
    return _event_loop


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
        # 使用持久事件循环（避免连接池失效）
        loop = _get_event_loop()
        result = loop.run_until_complete(
            _parse_document_async(self, doc_id, file_key, kb_id, stream_key)
        )
        return result

    except Exception as exc:
        logger.error(f"Parse task failed: doc_id={doc_id}, error={exc}")

        # 更新文档状态为 failed
        try:
            loop = _get_event_loop()
            loop.run_until_complete(_update_document_status(doc_id, "failed"))
        except Exception as update_error:
            logger.error(f"Failed to update document status: {update_error}")

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

    # 4.5 保存树节点到数据库
    await _save_tree_nodes_to_db(tree, doc_id)

    # 4.6 保存元素到数据库
    await _save_elements_to_db(parsed_doc.elements, doc_id, tree)

    # 5. 分块
    _publish_sync(stream_key, "task_progress", {
        "doc_id": doc_id,
        "pct": 60,
        "step": "chunking"
    })

    chunker = Chunker(chunk_size=512, chunk_overlap=50)
    chunks = await chunker.chunk(parsed_doc.elements, doc_id, kb_id)

    # 5.5 保存 chunks 到数据库
    await _save_chunks_to_db(chunks, doc_id, kb_id)

    # 6. 向量化
    _publish_sync(stream_key, "task_progress", {
        "doc_id": doc_id,
        "pct": 80,
        "step": "embedding",
        "chunk_count": len(chunks)
    })

    embedder = Embedder()
    vector_count = await embedder.embed(chunks, kb_id)

    # 6.5 更新文档状态为 done
    await _update_document_status(doc_id, "done")

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


async def _save_chunks_to_db(chunks: list[dict], doc_id: str, kb_id: str) -> int:
    """保存 chunks 到数据库

    Args:
        chunks: 分块列表（字典格式）
        doc_id: 文档 ID
        kb_id: 知识库 ID

    Returns:
        保存的 chunk 数量
    """
    import uuid
    from app.models.chunk import Chunk
    from app.models.document import Document

    if not chunks:
        return 0

    async with async_session() as session:
        # 更新文档的分块数量、元素数量和状态
        doc_uuid = uuid.UUID(doc_id)
        doc = await session.get(Document, doc_uuid)
        if doc:
            doc.chunk_count = len(chunks)
            # 计算元素数量（从第一个 chunk 的 metadata 中获取）
            if chunks and "metadata" in chunks[0]:
                element_ids = chunks[0]["metadata"].get("element_ids", [])
                doc.element_count = len(element_ids)
            # 更新状态为 parsing（向量化完成后会更新为 done）
            doc.status = "parsing"

        # 插入 chunks
        for idx, chunk_dict in enumerate(chunks):
            # 生成 chunk ID
            chunk_id = uuid.uuid4()

            # 确保 kb_id 是字符串类型（数据库字段是 String(36)）
            chunk = Chunk(
                id=chunk_id,  # 显式设置 ID
                document_id=uuid.UUID(chunk_dict["doc_id"]),
                kb_id=str(chunk_dict["kb_id"]),  # ← 转换为字符串
                content=chunk_dict["content"],
                content_search=chunk_dict["content"],  # ← 填充全文检索字段
                seq=idx,
                char_count=len(chunk_dict["content"]),
                metadata_=chunk_dict.get("metadata", {}),
                enabled=True
            )
            session.add(chunk)

            # 更新 chunk_dict 以便后续 embedding 使用
            chunk_dict["id"] = str(chunk_id)

        await session.commit()
        logger.info(f"Saved {len(chunks)} chunks to database: doc_id={doc_id}")
        return len(chunks)


async def _update_document_status(doc_id: str, status: str) -> None:
    """更新文档状态

    Args:
        doc_id: 文档 ID
        status: 新状态（done/failed）
    """
    import uuid
    from app.models.document import Document

    async with async_session() as session:
        doc_uuid = uuid.UUID(doc_id)
        doc = await session.get(Document, doc_uuid)
        if doc:
            doc.status = status
            await session.commit()
            logger.info(f"Updated document status: doc_id={doc_id}, status={status}")


async def _save_tree_nodes_to_db(tree: "DocumentTree", doc_id: str) -> int:
    """保存树节点到数据库

    Args:
        tree: 文档树对象
        doc_id: 文档 ID

    Returns:
        保存的节点数量
    """
    import uuid
    from app.models.tree_node import TreeNode
    from app.core.parser.base import DocumentTree

    if not tree or not tree.nodes:
        return 0

    async with async_session() as session:
        # 创建节点ID映射
        node_id_map = {}  # node_id (str) -> UUID
        db_nodes_map = {}  # node_id (str) -> TreeNode object (内存引用)

        # 第一遍：创建所有节点并建立映射
        for idx, node in enumerate(tree.nodes):
            db_node_id = uuid.uuid4()
            node_id_map[node.node_id] = db_node_id

            # 创建TreeNode对象
            db_node = TreeNode(
                id=db_node_id,
                document_id=uuid.UUID(doc_id),
                parent_id=None,  # 先设为None，第二遍更新
                level=node.level,
                sort_order=idx,  # 按顺序设置
                title=node.title[:500] if node.title else "Untitled",  # 限制长度
                summary=node.title,  # 暂时用标题作为摘要
                element_count=len(node.element_ids) if node.element_ids else 0,
            )
            session.add(db_node)
            # 保存到内存映射，避免后续查询
            db_nodes_map[node.node_id] = db_node

        await session.flush()  # 获取所有ID

        # 第二遍：更新parent_id（直接在内存中操作，避免 session.get()）
        for node in tree.nodes:
            if node.children:
                parent_db_id = node_id_map[node.node_id]
                for child_node_id in node.children:
                    if child_node_id in db_nodes_map:
                        # 直接在内存中操作对象，避免数据库查询
                        db_nodes_map[child_node_id].parent_id = parent_db_id

        await session.commit()
        logger.info(f"Saved {len(tree.nodes)} tree nodes to database: doc_id={doc_id}")
        return len(tree.nodes)


async def _save_elements_to_db(elements: list, doc_id: str, tree: "DocumentTree") -> int:
    """保存元素到数据库

    Args:
        elements: 文档元素列表
        doc_id: 文档 ID
        tree: 文档树对象（用于关联元素到树节点）

    Returns:
        保存的元素数量
    """
    import uuid
    from app.models.tree_node import ElementPosition, TreeNode
    from app.core.parser.base import DocumentElement, DocumentTree

    if not elements:
        return 0

    async with async_session() as session:
        # 查询文档的所有树节点
        tree_nodes = await session.execute(
            select(TreeNode).where(TreeNode.document_id == uuid.UUID(doc_id))
        )
        tree_nodes = tree_nodes.scalars().all()

        # 构建元素ID到树节点数据库ID的映射
        # 从树节点的 element_ids 反向映射
        element_to_node_db_id = {}
        if tree_nodes and tree:
            # 建立树节点数据的 node_id 到数据库 ID 的映射
            # 首先建立标题到数据库节点的映射
            title_to_db_id = {node.title: node.id for node in tree_nodes}

            # 然后从树数据中找到每个节点对应的数据库ID
            for tree_node_data in tree.nodes:
                # 通过标题找到数据库节点ID
                db_node_id = title_to_db_id.get(tree_node_data.title)
                if db_node_id:
                    # 将该节点包含的所有元素映射到数据库节点ID
                    for element_id in tree_node_data.element_ids:
                        element_to_node_db_id[element_id] = db_node_id

        # 保存元素
        saved_count = 0
        for idx, elem in enumerate(elements):
            # 确保 elem 是 DocumentElement 类型
            if not isinstance(elem, DocumentElement):
                continue

            # 查找该元素应该关联的树节点
            tree_node_db_id = element_to_node_db_id.get(elem.element_id)

            # 创建ElementPosition记录
            db_elem = ElementPosition(
                id=uuid.uuid4(),
                document_id=uuid.UUID(doc_id),
                chunk_id=None,  # 后续关联
                tree_node_id=tree_node_db_id,  # 关联树节点
                element_type=elem.element_type,
                element_index=idx,
                page_number=elem.position.page if elem.position else None,
                content=elem.content[:10000] if elem.content else None,  # 限制长度
                image_key=None,  # 图片键（如果有）
                ocr_text=None,  # OCR文本（如果有）
                metadata_=elem.metadata or {}
            )
            session.add(db_elem)
            saved_count += 1

        await session.commit()
        logger.info(f"Saved {saved_count} elements to database: doc_id={doc_id}")
        return saved_count


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def execute_retrieval_test(self, run_id: str) -> dict:
    """
    检索测试任务

    执行检索测试并返回结果

    Args:
        run_id: 测试运行 ID

    Returns:
        测试结果
    """
    from app.services import retrieval_test_service

    stream_key = f"retrieval_test:{run_id}"

    try:
        _publish_sync(stream_key, "task_started", {
            "run_id": run_id,
            "pct": 0
        })

        # 执行检索测试
        # 使用持久事件循环
        loop = _get_event_loop()
        loop.run_until_complete(
            retrieval_test_service.execute_run(run_id)
        )

        _publish_sync(stream_key, "task_completed", {
            "run_id": run_id,
            "pct": 100
        })

        logger.info(f"Retrieval test completed: run_id={run_id}")
        return {"run_id": run_id, "status": "success"}

    except Exception as exc:
        logger.error(f"Retrieval test failed: run_id={run_id}, error={exc}")

        _publish_sync(stream_key, "task_failed", {
            "run_id": run_id,
            "error": str(exc),
            "retry_count": self.request.retries
        })

        # 重试
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))

        raise


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def reembed_chunks(self, kb_id: str, document_ids: list[str], chunk_ids: list[str]) -> dict:
    """
    重建索引任务

    重新向量化指定的 chunks

    Args:
        kb_id: 知识库 ID (UUID 字符串)
        document_ids: 文档 ID 列表
        chunk_ids: 分块 ID 列表

    Returns:
        重建结果: {success: bool, updated: int}
    """
    stream_key = f"reembed:{kb_id}"

    try:
        # 使用持久事件循环
        loop = _get_event_loop()
        result = loop.run_until_complete(_reembed_chunks_async(kb_id, document_ids, chunk_ids))

        _publish_sync(stream_key, "task_completed", {
            "kb_id": kb_id,
            "updated": result["updated"]
        })

        logger.info(f"Reembed task completed: kb_id={kb_id}, updated={result['updated']}")
        return result

    except Exception as exc:
        logger.error(f"Reembed task failed: kb_id={kb_id}, error={exc}")

        _publish_sync(stream_key, "task_failed", {
            "kb_id": kb_id,
            "error": str(exc)
        })

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60)

        raise


async def _reembed_chunks_async(kb_id: str, document_ids: list[str], chunk_ids: list[str]) -> dict:
    """异步重建索引"""
    import uuid
    from sqlalchemy import select
    from app.models.chunk import Chunk

    # 1. 查询需要重建的 chunks
    async with async_session() as session:
        query = select(Chunk).where(Chunk.kb_id == kb_id)

        if document_ids:
            doc_uuids = [uuid.UUID(doc_id) for doc_id in document_ids]
            query = query.where(Chunk.document_id.in_(doc_uuids))

        if chunk_ids:
            chunk_uuids = [uuid.UUID(chunk_id) for chunk_id in chunk_ids]
            query = query.where(Chunk.id.in_(chunk_uuids))

        chunks = (await session.execute(query)).scalars().all()

    if not chunks:
        return {"success": True, "updated": 0}

    # 2. 获取 embedding 模型
    from app.core.parser.embedder import Embedder
    embedder = Embedder()

    # 3. 准备 chunk 数据
    chunk_data = [
        {
            "id": str(chunk.id),
            "content": chunk.content,
            "document_id": str(chunk.document_id),
            "kb_id": chunk.kb_id
        }
        for chunk in chunks
    ]

    # 4. 重新向量化
    updated = await embedder.embed(chunk_data, kb_id)

    return {"success": True, "updated": updated}


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
