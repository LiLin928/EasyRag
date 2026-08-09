"""settings_service（默认模型读取 + 同组互斥 + upsert）单元测试。"""
import pytest
from sqlalchemy import delete

from app.db.session import async_session
from app.models.model_config import ModelConfig
from app.services.settings_service import get_default_model, set_default_model, upsert_model


async def _clear_llm():
    """清理 llm 组所有记录，保证各测试从干净状态起步（测试共享真实库，需幂等）。"""
    async with async_session() as s:
        await s.execute(delete(ModelConfig).where(ModelConfig.grp == "llm"))
        await s.commit()


@pytest.mark.asyncio
async def test_get_default_by_use_then_group():
    """配置一个 use=qa 的 llm 默认模型；查 rewrite 应回退到该组默认，查 qa 应直接命中。"""
    await _clear_llm()
    await upsert_model(ModelConfig(grp="llm", name="qwen-plus", prov="dashscope", use="qa", is_default=True))
    m = await get_default_model("llm", "rewrite")
    assert m is not None and m.name == "qwen-plus"
    m2 = await get_default_model("llm", "qa")
    assert m2.name == "qwen-plus"


@pytest.mark.asyncio
async def test_set_default_is_exclusive_within_group():
    """set_default 应在同组内互斥：置 b 为默认后，b 成为组内唯一默认。"""
    await _clear_llm()
    await upsert_model(ModelConfig(grp="llm", name="a", prov="openai", is_default=True))
    await upsert_model(ModelConfig(grp="llm", name="b", prov="openai", is_default=False))
    await set_default_model("llm", "b")
    a = await get_default_model("llm")
    assert a.name == "b"
