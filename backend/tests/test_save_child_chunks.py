"""子分段保存逻辑的单元测试（方案§9：父子分段）。

聚焦验证 _save_child_chunks_to_db 在保存子分段时同步更新
document.chunk_count 与 status，避免文档列表"分段数"列对父子
分段文档显示旧值/0。
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.document import Document
from app.worker.tasks.parse_tasks import _save_child_chunks_to_db


@pytest.mark.asyncio
async def test_save_child_chunks_updates_document_chunk_count():
    """保存子分段时应更新 document.chunk_count 与 status。"""
    doc_id = str(uuid.uuid4())
    kb_id = str(uuid.uuid4())
    node_id = str(uuid.uuid4())

    doc = MagicMock(spec=Document)
    doc.id = uuid.UUID(doc_id)
    doc.chunk_count = 0
    doc.status = "pending"

    fake_session = AsyncMock()
    # 调用顺序：先 session.get(Document, ...)（更新分段数），后 session.get(TreeNode, ...)（节点不存在跳过）
    fake_session.get = AsyncMock(side_effect=[doc, None])

    class _Ctx:
        async def __aenter__(self):
            return fake_session

        async def __aexit__(self, *args):
            return None

    child_chunks = [
        {
            "doc_id": doc_id,
            "kb_id": kb_id,
            "tree_node_id": node_id,
            "position": 1,
            "content": "一段子分段内容",
            "char_count": 8,
            "metadata": {},
        },
        {
            "doc_id": doc_id,
            "kb_id": kb_id,
            "tree_node_id": node_id,
            "position": 2,
            "content": "另一段子分段内容",
            "char_count": 9,
            "metadata": {},
        },
    ]

    with patch("app.worker.tasks.parse_tasks.async_session", return_value=_Ctx()):
        n = await _save_child_chunks_to_db(child_chunks, doc_id, kb_id)

    assert n == 2
    assert doc.chunk_count == 2
    assert doc.status == "parsing"


@pytest.mark.asyncio
async def test_save_child_chunks_empty_list_returns_zero():
    """空子分段列表直接返回 0，不触碰数据库。"""
    n = await _save_child_chunks_to_db([], str(uuid.uuid4()), str(uuid.uuid4()))
    assert n == 0
