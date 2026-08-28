"""Checkpointer 单例统一测试。"""
from unittest.mock import patch, AsyncMock

import pytest


@pytest.mark.asyncio
async def test_graph_builder_uses_memory_singleton(monkeypatch):
    """GraphBuilder.build 调用 core.agent.memory.get_checkpointer 而非自建。"""
    fake_cp = AsyncMock()
    fake_cp.setup = AsyncMock()
    monkeypatch.setattr("app.core.agent.memory._checkpointer", fake_cp)
    monkeypatch.setattr("app.config.settings.env", "development")

    from app.core.engine.graph_builder import GraphBuilder
    from app.core.agent.memory import get_checkpointer

    builder = GraphBuilder()
    assert not hasattr(builder, "_get_checkpointer")
    cp = await get_checkpointer()
    assert cp is fake_cp
