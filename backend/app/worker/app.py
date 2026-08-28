"""ARQ worker 配置 + parse_document_task（解析→分块→建树→向量化）。"""
import time
from datetime import datetime

import os
import tempfile
import uuid as uuid_lib

from arq.connections import RedisSettings
from sqlalchemy import select, update

from app.config import settings
from app.core.engine.graph_builder import GraphBuilder
from app.core.engine.sse_bus import publish
from app.core.parser.chunker import chunk as do_chunk
from app.core.parser.dispatcher import parse as parse_file
from app.core.parser.tree_builder import build_tree
from app.db.session import async_session
from app.models.chunk import Chunk
from app.models.document import Document, ParseTask
from app.models.knowledge_base import KnowledgeBase
from app.models.tree_node import ElementPosition, TreeNode
from app.models.workflow import Workflow, WorkflowExecution, WorkflowVersion
from app.exceptions import BizException, ErrorCode
from app.providers.langchain_factory import (
    build_embeddings,
    build_embeddings_from_config,
    get_model_by_id,
)
from app.providers.storage.factory import get_storage
from app.services.retrieval_test_service import execute_run
from app.services.settings_service import get_default_model


REEMBED_BATCH_SIZE = 32


async def startup(ctx):
    """worker 启动钩子。"""
    ctx["ok"] = True
    # Phase 3: 提前初始化 checkpointer，避免首个任务冷启动
    from app.core.agent.memory import init_checkpointer_for_worker
    await init_checkpointer_for_worker()


async def _set_status(doc_id: str, status: str, pct: int, error: str | None = None):
    """同步更新 Document 与 ParseTask 的解析状态/进度/错误。"""
    async with async_session() as s:
        await s.execute(update(Document).where(Document.id == doc_id)
                        .values(status=status, pct=pct, error=error))
        await s.execute(update(ParseTask).where(ParseTask.doc_id == doc_id)
                        .values(status=status, pct=pct, error=error))
        await s.commit()


async def _kb_embedding_model(kb: KnowledgeBase):
    if kb.embedding_model_id:
        return await get_model_by_id(kb.embedding_model_id, "embed")
    return None


async def _embeddings_for_kb(kb: KnowledgeBase):
    try:
        explicit_model = await _kb_embedding_model(kb)
        if explicit_model is not None:
            embeddings = await build_embeddings_from_config(explicit_model)
            return embeddings, explicit_model.name
        embeddings = await build_embeddings()
        default_model = (
            await get_default_model("embed", "retrieval")
            or await get_default_model("embed")
        )
        if default_model is None:
            raise BizException(
                ErrorCode.DEPENDENCY_DOWN, "未配置默认 Embedding 模型，请在设置页配置"
            )
        return embeddings, default_model.name
    except BizException as exc:
        message = (
            "知识库绑定的 Embedding 模型不可用"
            if kb.embedding_model_id
            else "系统 Embedding 模型不可用"
        )
        raise RuntimeError(message) from exc


def _uuid_values(values: list[str], label: str) -> list[uuid_lib.UUID]:
    parsed = []
    for value in values:
        try:
            parsed.append(uuid_lib.UUID(str(value)))
        except (TypeError, ValueError) as exc:
            raise BizException(ErrorCode.PARAM_ERROR, f"无效的{label}") from exc
    return parsed


async def parse_document_task(ctx, doc_id: str):
    """ARQ 任务：解析文档 → 分块 → 建树 → 批量向量化。失败自动重试（max_tries=3）。"""
    doc_id_s = doc_id  # 预置，保证 except 中可引用
    try:
        async with async_session() as s:
            doc = (await s.execute(select(Document).where(Document.id == doc_id))).scalar_one()
            kb = (await s.execute(select(KnowledgeBase).where(KnowledgeBase.id == doc.kb_id))).scalar_one()
            doc_id_s, kb_id_s, ext, file_key = str(doc.id), str(kb.id), doc.ext, doc.file_key
            chunk_size, overlap = kb.chunk_size, kb.chunk_overlap

        embeddings, embedding_model_name = await _embeddings_for_kb(kb)

        await _set_status(doc_id_s, "parsing", 5)

        storage = get_storage()
        data = await storage.get(file_key)
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tf:
            tf.write(data)
            tmp_path = tf.name

        elements = await parse_file(ext, tmp_path)
        os.unlink(tmp_path)
        await _set_status(doc_id_s, "parsing", 40)

        chunks_data = do_chunk(elements, chunk_size=chunk_size, overlap=overlap)
        await _set_status(doc_id_s, "parsing", 55)

        chunk_objs: list[Chunk] = []
        async with async_session() as s:
            for cd in chunks_data:
                c = Chunk(document_id=doc_id_s, kb_id=kb_id_s, content=cd["content"],
                          content_search=cd["content_search"], page_number=cd["page_number"],
                          section_path=cd["section_path"], clause_title=cd["clause_title"], seq=cd["seq"])
                c.metadata_ = {}
                c.char_count = len(cd["content"])
                s.add(c)
                chunk_objs.append(c)
            await s.flush()
            for i, e in enumerate(elements):
                s.add(ElementPosition(document_id=doc_id_s, element_type=e.element_type, element_index=i,
                                      page_number=e.page_number, content=e.content,
                                      metadata_={"section_path": e.section_path}))
            await s.commit()
        await _set_status(doc_id_s, "parsing", 70)

        tree_nodes = await build_tree(doc_id_s, elements)
        await _set_status(doc_id_s, "parsing", 80)

        if chunk_objs:
            vecs = await embeddings.aembed_documents([c.content for c in chunk_objs])
            async with async_session() as s:
                for c, v in zip(chunk_objs, vecs):
                    await s.execute(update(Chunk).where(Chunk.id == c.id)
                                    .values(embedding=v, embedding_model=embedding_model_name))
                await s.commit()
        if tree_nodes:
            nav_vecs = await embeddings.aembed_documents([n.title for n in tree_nodes])
            async with async_session() as s:
                for n, v in zip(tree_nodes, nav_vecs):
                    await s.execute(update(TreeNode).where(TreeNode.id == n.id).values(nav_embedding=v))
                await s.commit()

        async with async_session() as s:
            await s.execute(update(Document).where(Document.id == doc_id_s).values(
                status="done", pct=100, chunk_count=len(chunk_objs), element_count=len(elements)))
            await s.commit()
        await _set_status(doc_id_s, "done", 100)
    except Exception as e:
        await _set_status(doc_id_s, "failed", 100, error=str(e))
        raise


async def reembed_chunks_task(
    ctx, kb_id: str, document_ids: list[str], chunk_ids: list[str]
):
    """ARQ task: rebuild selected chunk vectors with the KB-bound model."""
    try:
        kb_uuid = _uuid_values([kb_id], "知识库 ID")[0]
    except BizException as exc:
        raise ValueError(str(exc.message)) from exc
    document_uuids = _uuid_values(document_ids, "文档 ID")
    chunk_uuids = _uuid_values(chunk_ids, "分块 ID")

    async with async_session() as session:
        kb = (
            await session.execute(
                select(KnowledgeBase).where(KnowledgeBase.id == kb_uuid)
            )
        ).scalar_one()

    embeddings, embedding_model_name = await _embeddings_for_kb(kb)

    query = (
        select(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .join(KnowledgeBase, Document.kb_id == KnowledgeBase.id)
        .where(
            KnowledgeBase.id == kb_uuid,
            Document.kb_id == kb_uuid,
            Chunk.kb_id == str(kb_uuid),
        )
        .order_by(Chunk.document_id, Chunk.seq, Chunk.id)
    )
    if document_uuids:
        query = query.where(Chunk.document_id.in_(document_uuids))
    if chunk_uuids:
        query = query.where(Chunk.id.in_(chunk_uuids))

    async with async_session() as session:
        selected = (
            await session.execute(query)
        ).scalars().all()

    selected_info = [(chunk.id, chunk.content) for chunk in selected]
    for offset in range(0, len(selected_info), REEMBED_BATCH_SIZE):
        batch = selected_info[offset : offset + REEMBED_BATCH_SIZE]
        vectors = await embeddings.aembed_documents(
            [content for _, content in batch]
        )
        if len(vectors) != len(batch):
            raise RuntimeError("Embedding provider returned an invalid batch size")
        async with async_session() as session:
            rows = (
                await session.execute(
                    select(Chunk)
                    .where(Chunk.id.in_([chunk_id for chunk_id, _ in batch]))
                    .with_for_update(of=Chunk)
                )
            ).scalars().all()
            by_id = {chunk.id: chunk for chunk in rows}
            for (chunk_id, _), vector in zip(batch, vectors):
                chunk = by_id.get(chunk_id)
                if chunk is None:
                    raise RuntimeError("Chunk disappeared while reindexing")
                chunk.embedding = vector
                chunk.embedding_model = embedding_model_name
            await session.commit()


async def run_retrieval_test_task(ctx, run_id: str):
    """ARQ task: execute one persisted retrieval regression run."""
    await execute_run(run_id)


async def execute_workflow_task(ctx, execution_id: str):
    """ARQ 任务：从 checkpoint 执行或恢复工作流。

    1. 从 DB 加载 execution + workflow definition
    2. 构建 graph（使用 PostgresSaver 单例 checkpointer）
    3. 检查 checkpoint：有 -> astream(None) 断点恢复；无 -> astream(initial) 全新执行
    4. astream 循环：每个节点完成 -> publish 到 Redis Stream
    5. 每轮检查 DB status == "cancelled" -> break
    6. 完成/失败/暂停 -> 更新 DB + publish 最终事件
    """
    try:
        # 1. 加载 execution + workflow + version
        async with async_session() as s:
            execution = (
                await s.execute(
                    select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
                )
            ).scalar_one_or_none()
            if not execution:
                return

            wf = (
                await s.execute(select(Workflow).where(Workflow.id == execution.workflow_id))
            ).scalar_one_or_none()
            if not wf:
                await _finish_execution(execution_id, "failed", error="工作流不存在")
                await publish(execution_id, "error", {"message": "工作流不存在"})
                return

            version = wf.current_version
            definition = wf.definition or {}
            if version > 0:
                ver = (
                    await s.execute(
                        select(WorkflowVersion)
                        .where(WorkflowVersion.workflow_id == wf.id)
                        .where(WorkflowVersion.version == version)
                    )
                ).scalar_one_or_none()
                if ver:
                    definition = ver.definition_snapshot or definition

            exec_id = str(execution.id)
            wf_id = str(execution.workflow_id)
            user_id = str(execution.user_id) if execution.user_id else ""
            inputs = execution.inputs or {}
            debug = False

        # 2. 发布开始事件
        await publish(exec_id, "execution_start", {"total_nodes": len(definition.get("nodes", []))})

        # 3. 构建 graph
        builder = GraphBuilder()
        graph = await builder.build(definition, exec_id, debug)

        config = {"configurable": {"thread_id": exec_id}}

        # 4. 检查 checkpoint
        snapshot = await graph.aget_state(config)
        has_checkpoint = snapshot and snapshot.next

        initial = {
            "workflow_id": wf_id, "execution_id": exec_id, "thread_id": exec_id,
            "user_id": user_id, "variables": inputs,
            "node_outputs": {}, "status": "running", "started_at": time.time(),
            "node_timings": {}, "debug_mode": debug, "loop_stack": [],
        }

        stream_input = None if has_checkpoint else initial

        # 5. astream 循环
        t0 = time.perf_counter()
        try:
            async for ev in graph.astream(stream_input, config=config, stream_mode="updates"):
                for nid, update in ev.items():
                    if nid in ("__start__", "__end__"):
                        continue
                    await publish(exec_id, "node_start", {"nodeId": nid})
                    await publish(exec_id, "node_complete", {
                        "nodeId": nid,
                        "output": str(update.get("node_outputs", {}).get(nid, {}))[:500],
                    })
                    if update.get("status") == "paused":
                        await _finish_execution(exec_id, "paused")
                        await publish(exec_id, "execution_paused", {"nodeId": nid})
                        return
                # 每轮检查 cancel
                if await _is_cancelled(exec_id):
                    await _finish_execution(exec_id, "cancelled")
                    await publish(exec_id, "execution_cancelled", {"executionId": exec_id})
                    return
        except Exception as e:
            duration = round((time.perf_counter() - t0) * 1000, 1)
            await _finish_execution(exec_id, "failed", error=str(e), duration_ms=duration)
            await publish(exec_id, "error", {"message": str(e)})
            raise  # 让 ARQ 重试

        # 6. 完成
        duration = round((time.perf_counter() - t0) * 1000, 1)
        await _finish_execution(exec_id, "completed", duration_ms=duration)
        await publish(exec_id, "execution_complete", {"success": True, "duration_ms": duration})

    except Exception as e:
        await _finish_execution(execution_id, "failed", error=str(e))
        await publish(execution_id, "error", {"message": str(e)})
        raise


async def _is_cancelled(execution_id: str) -> bool:
    """检查 execution 是否被 cancel。"""
    async with async_session() as s:
        ex = (
            await s.execute(
                select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
            )
        ).scalar_one_or_none()
    return ex and ex.status == "cancelled"


async def _finish_execution(
    exec_id: str, status: str, error: str | None = None, duration_ms: float | None = None
):
    """更新执行记录状态。"""
    async with async_session() as s:
        ex = (
            await s.execute(
                select(WorkflowExecution).where(WorkflowExecution.id == exec_id)
            )
        ).scalar_one_or_none()
        if ex:
            ex.status = status
            ex.error = error
            ex.duration_ms = duration_ms
            ex.completed_at = datetime.now() if status in ("completed", "failed", "cancelled") else None
            await s.commit()


class WorkerSettings:
    """ARQ WorkerSettings。"""

    functions = [
        parse_document_task,
        reembed_chunks_task,
        run_retrieval_test_task,
        execute_workflow_task,
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    max_jobs = 4
    job_timeout = 600
    max_tries = 3
