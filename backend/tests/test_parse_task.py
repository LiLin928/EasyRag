"""parse_document_task（ARQ 核心任务）单元测试。"""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete, select

from app.db.session import async_session
from app.models.chunk import Chunk
from app.models.document import Document, ParseTask
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.providers.storage.factory import get_storage
from app.worker.app import parse_document_task


@pytest.mark.asyncio
async def test_parse_task_end_to_end(tmp_path, monkeypatch):
    """端到端：建 doc + 假 md 文件 → mock embedding → 解析→分块→建树→向量化。"""
    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(KnowledgeBase.name == "ParseTask_KB"))
        await s.commit()
        u = (await s.execute(select(User))).scalars().first()
        kb = KnowledgeBase(user_id=u.id, name="ParseTask_KB", scene="general")
        s.add(kb)
        await s.flush()
        doc = Document(kb_id=kb.id, user_id=u.id, name="t.md", ext="md", size=10, mode="fast",
                       status="pending", file_key=f"{kb.id}/t.md")
        s.add(doc)
        await s.flush()
        doc.file_key = f"{kb.id}/{doc.id}/t.md"
        task = ParseTask(doc_id=doc.id, kb_id=str(kb.id), status="pending")
        s.add(task)
        await s.commit()
        doc_id, key = str(doc.id), doc.file_key

    monkeypatch.setattr("app.config.settings.storage_local_dir", str(tmp_path))
    st = get_storage()
    await st.put(key, "# 标题\n正文内容\n".encode("utf-8"))

    # mock embedding（返回固定 1024 维向量）
    fake_emb = AsyncMock()
    fake_emb.aembed_documents = AsyncMock(return_value=[[0.1] * 1024, [0.2] * 1024])
    with patch("app.worker.app.build_embeddings", AsyncMock(return_value=fake_emb)):
        await parse_document_task({}, doc_id)

    async with async_session() as s:
        d = (await s.execute(select(Document).where(Document.id == doc_id))).scalar_one()
        assert d.status == "done" and d.pct == 100
        assert d.chunk_count >= 1
        chunks = (await s.execute(select(Chunk).where(Chunk.document_id == doc_id))).scalars().all()
        assert len(chunks) >= 1
        assert chunks[0].embedding is not None
