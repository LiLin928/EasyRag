"""langchain_factory（build_chat_model / build_embeddings）单元测试。"""
import pytest
from sqlalchemy import delete

from app.db.session import async_session
from app.models.model_config import ModelConfig
from app.providers.langchain_factory import build_chat_model
from app.security.crypto import encrypt
from app.services.settings_service import upsert_model


async def _clear_llm():
    """清理 llm 组，保证测试从干净状态起步（共享真实库幂等）。"""
    async with async_session() as s:
        await s.execute(delete(ModelConfig).where(ModelConfig.grp == "llm"))
        await s.commit()


@pytest.mark.asyncio
async def test_build_chat_model_uses_default(monkeypatch):
    """build_chat_model 应读取 (llm, qa) 默认配置，并以 openai provider + base_url 构造模型。"""
    await _clear_llm()
    await upsert_model(ModelConfig(
        grp="llm", name="qwen-plus", prov="dashscope", use="qa",
        url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key_enc=encrypt("sk-test"), is_default=True, params={"temp": 0.3}))

    captured = {}

    def fake_init(model, model_provider, **kw):
        captured.update(kw)
        captured["model"] = model
        captured["provider"] = model_provider

        class _Dummy:
            pass
        return _Dummy()

    monkeypatch.setattr("app.providers.langchain_factory.init_chat_model", fake_init)
    await build_chat_model(use="qa")
    assert captured["provider"] == "openai"
    assert captured["model"] == "qwen-plus"
    assert captured["base_url"].endswith("/compatible-mode/v1")


@pytest.mark.asyncio
async def test_build_chat_model_no_default_raises():
    """无默认 llm 模型时，build_chat_model 应抛业务异常（引导用户去设置页配置）。"""
    await _clear_llm()
    with pytest.raises(Exception):
        await build_chat_model(use="qa")
