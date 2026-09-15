"""父子分段元数据保存的回归测试。

回归场景：父子模式下在 segments 标签设置元数据不生效，因为元数据更新
只查/写 chunks 表，而父子分段的行在 child_chunks 表（主键不互通）。
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import asset_service


def _patch_session(session):
    """构造一个替换 async_session() 的上下文管理器 patch。"""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return patch.object(asset_service, "async_session", return_value=ctx)


@pytest.mark.asyncio
async def test_batch_update_metadata_child_chunk_scope_targets_child_chunks_table():
    """scope='child_chunk' 的批量元数据更新必须查 child_chunks 表。"""
    captured = []
    mock_result = MagicMock()
    mock_result.all.return_value = []  # 空结果 → 提前返回，但 select 已执行

    session = AsyncMock()

    async def _exec(stmt, *a, **kw):
        captured.append(stmt)
        return mock_result

    session.execute = AsyncMock(side_effect=_exec)
    session.commit = AsyncMock()

    with _patch_session(session):
        updated = await asset_service.batch_update_metadata(
            [str(uuid.uuid4())], uuid.uuid4(), "child_chunk", {"foo": "bar"}
        )

    assert updated == 0
    assert captured, "应执行一次 select 查询"
    sql = str(captured[0].compile(compile_kwargs={"literal_binds": True})).lower()
    assert "child_chunks" in sql


@pytest.mark.asyncio
async def test_update_child_chunk_metadata_writes_metadata_onto_child_chunk():
    """单条子分段元数据更新应把清洗后的 metadata 写到 ChildChunk 对象。"""
    from app.models.child_chunk import ChildChunk

    child = MagicMock(spec=ChildChunk)
    child.id = uuid.uuid4()
    child.kb_id = str(uuid.uuid4())
    child.metadata_ = {}

    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock(return_value=None)

    user_id = uuid.uuid4()
    with _patch_session(session), \
         patch.object(asset_service, "_child_chunk_from", new=AsyncMock(return_value=child)), \
         patch.object(asset_service, "_clean_metadata", new=AsyncMock(return_value={"foo": "bar"})):
        result = await asset_service.update_child_chunk_metadata(
            str(child.id), user_id, {"foo": "bar"}
        )

    assert result is child
    assert child.metadata_ == {"foo": "bar"}
    session.commit.assert_awaited()
