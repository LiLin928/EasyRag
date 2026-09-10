"""Tracing provider（可切换 LangSmith / 自部署 Langfuse / none）。

提供：
- configure_tracing(): 配置 tracing provider
- get_tracing_callbacks(): 获取 callbacks
- traced_span(): 嵌套 span 上下文管理器
"""
from app.providers.trace.factory import (
    configure_tracing,
    get_tracing_callbacks,
)
from app.providers.trace.span_manager import (
    traced_span,
    get_current_span_context,
    set_span_context,
    SpanContext,
)

__all__ = [
    "configure_tracing",
    "get_tracing_callbacks",
    "traced_span",
    "get_current_span_context",
    "set_span_context",
    "SpanContext",
]
