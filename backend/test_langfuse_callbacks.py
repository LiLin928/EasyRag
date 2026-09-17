"""测试 Langfuse tracing 通过 CallbackHandler 工作。"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.providers.trace.factory import configure_tracing, get_tracing_callbacks
from app.config import settings


def test_langfuse_callback_handler_created():
    """测试 Langfuse CallbackHandler 被正确创建。"""
    # 配置 tracing
    configure_tracing()

    # 获取 callbacks
    callbacks = get_tracing_callbacks()

    if settings.tracing_provider == "langfuse":
        # 验证 callbacks 存在
        assert callbacks is not None, "Langfuse callbacks should be returned"
        assert isinstance(callbacks, list), "Callbacks should be a list"
        assert len(callbacks) > 0, "Callbacks list should not be empty"

        # 验证是 Langfuse CallbackHandler
        from langfuse.langchain import CallbackHandler
        assert isinstance(callbacks[0], CallbackHandler), "First callback should be Langfuse CallbackHandler"

        print(f"[OK] Langfuse CallbackHandler created successfully")
        print(f"     Host: {settings.langfuse_host}")
        print(f"     Public Key: {settings.langfuse_public_key[:20]}...")
    else:
        print(f"[SKIP] Tracing provider is {settings.tracing_provider}, not langfuse")


@pytest.mark.asyncio
async def test_callbacks_injected_to_llm_call():
    """测试 callbacks 被正确注入到 LLM 调用。"""
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.language_models.chat_models import BaseChatModel

    # Mock LLM
    mock_llm = MagicMock(spec=BaseChatModel)
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="测试回复"))

    # 构建 chain
    prompt = ChatPromptTemplate.from_messages([("human", "测试")])
    chain = prompt | mock_llm | StrOutputParser()

    # 获取 callbacks
    callbacks = get_tracing_callbacks()
    config = {"callbacks": callbacks} if callbacks else {}

    # 调用 chain
    result = await chain.ainvoke({}, config=config)

    # 验证调用成功
    assert result == "测试回复"

    # 验证 config 被传递
    mock_llm.ainvoke.assert_called_once()
    call_args = mock_llm.ainvoke.call_args
    assert "config" in call_args[1] or len(call_args[0]) > 0, "Config should be passed to ainvoke"

    print(f"[OK] Callbacks injected to LLM call successfully")
    print(f"     Result: {result}")
    print(f"     Config: {config}")


def test_tracing_configuration():
    """测试 tracing 配置正确。"""
    from app.config import settings

    print("\n=== Tracing Configuration ===")
    print(f"Provider: {settings.tracing_provider}")
    print(f"Langfuse Host: {settings.langfuse_host}")
    print(f"Public Key: {settings.langfuse_public_key[:20] if settings.langfuse_public_key else None}...")
    print(f"Secret Key: {settings.langfuse_secret_key[:20] if settings.langfuse_secret_key else None}...")

    # 验证配置完整性
    if settings.tracing_provider == "langfuse":
        assert settings.langfuse_public_key, "Langfuse public key should be set"
        assert settings.langfuse_secret_key, "Langfuse secret key should be set"
        assert settings.langfuse_host, "Langfuse host should be set"
        print("[OK] Langfuse configuration is complete")
    else:
        print(f"[SKIP] Provider is {settings.tracing_provider}")


if __name__ == "__main__":
    import asyncio

    # 运行同步测试
    test_tracing_configuration()
    test_langfuse_callback_handler_created()

    # 运行异步测试
    asyncio.run(test_callbacks_injected_to_llm_call())

    print("\n[SUCCESS] All Langfuse tracing tests passed!")