"""ARQ worker 配置 + parse_document_task（解析→分块→建树→向量化）。"""
import os
import tempfile

from arq.connections import RedisSettings
from sqlalchemy import select, update

from app.config import settings
from app.core.parser.chunker import chunk as do_chunk
from app.core.parser.dispatcher import parse as parse_file
from app.core.parser.tree_builder import build_tree
from app.db.session import async_session
from app.models.chunk import Chunk
from app.models.document import Document, ParseTask
from app.models.knowledge_base import KnowledgeBase
from app.models.tree_node import ElementPosition, TreeNode
from app.providers.langchain_factory import build_embeddings
from app.providers.storage.factory import get_storage


async def startup(ctx):
    """worker 启动钩子。"""
    ctx["ok"] = True


async def _set_status(doc_id: str, status: str, pct: int, error: str | None = None):
    """同步更新 Document 与 ParseTask 的解析状态/进度/错误。"""
    async with async_session() as s:
        await s.execute(update(Document).where(Document.id == doc_id)
                        .values(status=status, pct=pct, error=error))
        await s.execute(update(ParseTask).where(ParseTask.doc_id == doc_id)
                        .values(status=status, pct=pct, error=error))
        await s.commit()


async def parse_document_task(ctx, doc_id: str):
    """ARQ 任务：解析文档 → 分块 → 建树 → 批量向量化。失败自动重试（max_tries=3）。"""
    doc_id_s = doc_id  # 预置，保证 except 中可引用
    try:
        async with async_session() as s:
            doc = (await s.execute(select(Document).where(Document.id == doc_id))).scalar_one()
            kb = (await s.execute(select(KnowledgeBase).where(KnowledgeBase.id == doc.kb_id))).scalar_one()
            doc_id_s, kb_id_s, ext, file_key = str(doc.id), str(kb.id), doc.ext, doc.file_key
            chunk_size, overlap = kb.chunk_size, kb.chunk_overlap

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

        emb = await build_embeddings()
        if chunk_objs:
            vecs = await emb.aembed_documents([c.content for c in chunk_objs])
            async with async_session() as s:
                for c, v in zip(chunk_objs, vecs):
                    await s.execute(update(Chunk).where(Chunk.id == c.id)
                                    .values(embedding=v, embedding_model="default"))
                await s.commit()
        if tree_nodes:
            nav_vecs = await emb.aembed_documents([n.title for n in tree_nodes])
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


class WorkerSettings:
    """ARQ WorkerSettings。"""

    functions = [parse_document_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    max_jobs = 4
    job_timeout = 600
    max_tries = 3
