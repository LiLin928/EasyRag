"""Tracing 工厂：启动时一次性配置可切换的 tracing（LangSmith / 自部署 Langfuse / none）。

注意（langchain 1.x / langfuse 4.x 与 plan 原方案的差异）：
plan 原方案依赖 ``langchain_core.globals.set_callbacks`` 全局注册回调，但
langchain 1.x 已移除该 API。故本实现改为：
- LangSmith：设置 ``LANGSMITH_*`` 环境变量，由 langsmith SDK 全局自动生效（无需 callbacks）。
- Langfuse（4.x，OTel）：设置 ``LANGFUSE_*`` 环境变量认证，并创建 LangchainCallbackHandler；
  langchain 1.x 无全局回调注册，故经 ``get_tracing_callbacks()`` 供业务侧 per-invocation 注入
  （config={"callbacks": ...}）。
"""
import os

from langfuse.langchain import CallbackHandler

from app.config import settings

_langfuse_handler = None


def configure_tracing() -> None:
    """根据 settings.tracing_provider 一次性配置 tracing（应用启动时调用一次）。

    - langsmith：设置 LANGSMITH_* 环境变量，LangChain 调用自动上报 LangSmith。
    - langfuse：设置 LANGFUSE_* 环境变量（4.x OTel 认证），并创建 LangchainCallbackHandler。
    - none：不采集（默认）。
    """
    global _langfuse_handler
    _langfuse_handler = None  # 每次配置从干净状态起，保证幂等
    p = settings.tracing_provider
    if p == "langsmith":
        os.environ["LANGSMITH_TRACING"] = "true"
        if settings.langsmith_api_key:
            os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        if settings.langsmith_endpoint:
            os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    elif p == "langfuse":
        if settings.langfuse_public_key:
            os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        if settings.langfuse_secret_key:
            os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
        if settings.langfuse_host:
            os.environ["LANGFUSE_HOST"] = settings.langfuse_host
        _langfuse_handler = CallbackHandler()
    # none: no-op


def get_tracing_callbacks() -> list | None:
    """返回应注入 LLM/链调用的 callbacks（业务侧 config={"callbacks": get_tracing_callbacks()}）。

    LangFuse 启用时返回 [handler]；LangSmith 经环境变量全局生效、无需 callbacks，返回 None。
    """
    if _langfuse_handler is not None:
        return [_langfuse_handler]
    return None
