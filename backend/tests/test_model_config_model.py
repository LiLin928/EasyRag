"""ModelConfig ORM 模型单元测试。"""
import pytest
from sqlalchemy import select

from app.db.session import async_session
from app.models.model_config import ModelConfig


@pytest.mark.asyncio
async def test_create_model_config():
    """创建一条模型配置，验证 JSONB params 与布尔默认值能正确持久化与读取。"""
    async with async_session() as s:
        m = ModelConfig(grp="llm", name="qwen-plus", prov="dashscope", use="qa",
                        url="http://x", api_key_enc="enc", params={"temp": 0.3}, is_default=True)
        s.add(m)
        await s.commit()
        got = (await s.execute(
            select(ModelConfig).where(ModelConfig.grp == "llm", ModelConfig.name == "qwen-plus")
        )).scalar_one()
        assert got.params["temp"] == 0.3
        assert got.is_default is True
