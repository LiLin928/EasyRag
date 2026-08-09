"""ModelConfig ORM 模型单元测试。"""
import pytest
from sqlalchemy import delete, select

from app.db.session import async_session
from app.models.model_config import ModelConfig


@pytest.mark.asyncio
async def test_create_model_config():
    """创建一条模型配置，验证 JSONB params 与布尔默认值能正确持久化与读取。

    使用测试专用 (grp, name) 并在开头清理可能残留的同名记录，保证测试可重复运行。
    """
    async with async_session() as s:
        await s.execute(delete(ModelConfig).where(
            ModelConfig.grp == "llm", ModelConfig.name == "test_model_unit"))
        await s.commit()
        m = ModelConfig(grp="llm", name="test_model_unit", prov="dashscope", use="qa",
                        url="http://x", api_key_enc="enc", params={"temp": 0.3}, is_default=True)
        s.add(m)
        await s.commit()
        got = (await s.execute(select(ModelConfig).where(
            ModelConfig.grp == "llm", ModelConfig.name == "test_model_unit"))).scalar_one()
        assert got.params["temp"] == 0.3
        assert got.is_default is True
