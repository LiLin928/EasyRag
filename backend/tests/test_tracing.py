"""tracing factory（configure_tracing / get_tracing_callbacks）单元测试。

langchain 1.x 无全局回调注册 API，故测试验证：环境变量设置（langsmith/langfuse）
与 langfuse handler 的创建，而非 plan 原方案的 set_callbacks 全局注册。
"""
import os
from unittest.mock import patch

from app.providers.trace.factory import configure_tracing, get_tracing_callbacks


def test_none_does_nothing(monkeypatch):
    """provider=none 时不设置任何 tracing 环境变量，也不创建回调。"""
    monkeypatch.setattr("app.providers.trace.factory.settings.tracing_provider", "none")
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    configure_tracing()
    assert "LANGSMITH_TRACING" not in os.environ
    assert get_tracing_callbacks() is None


def test_langsmith_sets_env(monkeypatch):
    """provider=langsmith 时设置 LANGSMITH_* 环境变量，由 langsmith SDK 全局生效。"""
    monkeypatch.setattr("app.providers.trace.factory.settings.tracing_provider", "langsmith")
    monkeypatch.setattr("app.providers.trace.factory.settings.langsmith_api_key", "k")
    monkeypatch.setattr("app.providers.trace.factory.settings.langsmith_project", "p")
    configure_tracing()
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_PROJECT"] == "p"
    assert get_tracing_callbacks() is None


def test_langfuse_sets_env_and_handler(monkeypatch):
    """provider=langfuse 时设置 LANGFUSE_* 环境变量并创建 LangchainCallbackHandler。"""
    monkeypatch.setattr("app.providers.trace.factory.settings.tracing_provider", "langfuse")
    monkeypatch.setattr("app.providers.trace.factory.settings.langfuse_public_key", "pk")
    monkeypatch.setattr("app.providers.trace.factory.settings.langfuse_secret_key", "sk")
    monkeypatch.setattr("app.providers.trace.factory.settings.langfuse_host", "http://x:3000")
    with patch("app.providers.trace.factory.CallbackHandler") as cb:
        configure_tracing()
        cb.assert_called_once()
    assert os.environ["LANGFUSE_PUBLIC_KEY"] == "pk"
    assert os.environ["LANGFUSE_HOST"] == "http://x:3000"
