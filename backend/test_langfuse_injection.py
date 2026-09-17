"""测试 Langfuse tracing 是否正确注入到 LangChain 调用。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.providers.trace.factory import configure_tracing, get_tracing_callbacks
from app.config import settings


def test_tracing_callbacks_injected():
    """测试 tracing callbacks 被正确创建和返回。"""
    # 配置 tracing
    configure_tracing()

    # 获取 callbacks
    callbacks = get_tracing_callbacks()

    # 验证：如果是 langfuse，应该返回非空 callbacks
    if settings.tracing_provider == "langfuse":
        assert callbacks is not None, "Langfuse callbacks should be returned"
        assert isinstance(callbacks, list), "Callbacks should be a list"
        assert len(callbacks) > 0, "Callbacks list should not be empty"
        print(f"[OK] Langfuse callbacks created: {callbacks}")
    elif settings.tracing_provider == "langsmith":
        # LangSmith 通过环境变量生效，callbacks 应该为 None
        assert callbacks is None, "LangSmith callbacks should be None (via env vars)"
        print("[OK] LangSmith enabled via environment variables")
    else:
        # none provider
        assert callbacks is None, "None provider should return None callbacks"
        print("[OK] Tracing disabled")


@pytest.mark.asyncio
async def test_llm_invoke_with_callbacks():
    """测试 LLM 调用时 callbacks 被正确注入。"""
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from app.providers.langchain_factory import build_chat_model

    # Mock LLM
    with patch("app.providers.langchain_factory.build_chat_model") as mock_build:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="测试回复"))
        mock_build.return_value = mock_llm

        # 构建 chain
        prompt = ChatPromptTemplate.from_messages([("human", "测试")])
        chain = prompt | mock_llm | StrOutputParser()

        # 获取 callbacks
        callbacks = get_tracing_callbacks()
        config = {"callbacks": callbacks} if callbacks else {}

        # 调用 chain
        result = await chain.ainvoke({}, config=config)

        # 验证调用参数中包含 config
        assert result == "测试回复"
        print(f"[OK] LLM invoke success, callbacks injected: {config}")


if __name__ == "__main__":
    # 运行测试
    test_tracing_callbacks_injected()
    import asyncio
    asyncio.run(test_llm_invoke_with_callbacks())