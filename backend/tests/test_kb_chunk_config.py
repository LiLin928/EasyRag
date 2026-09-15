"""知识库父子分段配置读取的单元测试（方案§9）。"""
import pytest

from app.worker.tasks.parse_tasks import _load_kb_chunk_config


@pytest.mark.asyncio
async def test_load_kb_chunk_config_invalid_uuid_returns_defaults():
    """非法 kb_id 返回默认配置（traditional/200/50），不抛异常。"""
    cfg = await _load_kb_chunk_config("not-a-uuid")
    assert cfg == {
        "retrieval_mode": "traditional",
        "child_chunk_size": 200,
        "child_chunk_overlap": 50,
    }


@pytest.mark.asyncio
async def test_load_kb_chunk_config_missing_kb_returns_defaults(tmp_path):
    """知识库不存在时返回默认配置。"""
    import uuid
    # 用一个合法但未占用的 UUID
    missing_id = str(uuid.uuid4())
    cfg = await _load_kb_chunk_config(missing_id)
    assert cfg["retrieval_mode"] == "traditional"
    assert cfg["child_chunk_size"] == 200
    assert cfg["child_chunk_overlap"] == 50
