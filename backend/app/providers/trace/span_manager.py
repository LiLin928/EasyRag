"""Tracing span 上下文管理器。

支持嵌套的 span 追踪，自动管理父子关系。

注意：Langfuse/LangSmith 的实际追踪由 LangChain CallbackHandler 自动处理。
本模块仅提供 span 上下文管理，用于本地调试和日志记录。
"""
import os
from contextlib import contextmanager
from typing import Optional
from dataclasses import dataclass, field
import contextvars
import time
import logging


logger = logging.getLogger(__name__)


@dataclass
class SpanContext:
    """Span 上下文。

    Attributes:
        trace_id: 追踪 ID（根 span ID）
        parent_span_id: 父 span ID
        current_span_id: 当前 span ID
        depth: 嵌套深度
        spans: 所有 span 列表
    """
    trace_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    current_span_id: Optional[str] = None
    depth: int = 0
    spans: list = field(default_factory=list)


# 线程本地存储（协程安全需要 contextvars）
_span_context: contextvars.ContextVar[Optional[SpanContext]] = contextvars.ContextVar(
    "span_context", default=None
)


def get_current_span_context() -> Optional[SpanContext]:
    """获取当前 span 上下文。

    Returns:
        当前 SpanContext 或 None
    """
    return _span_context.get()


def set_span_context(ctx: Optional[SpanContext]) -> None:
    """设置 span 上下文。

    Args:
        ctx: 要设置的 SpanContext
    """
    _span_context.set(ctx)


@contextmanager
def traced_span(
    name: str,
    kind: str = "INTERNAL",
    attributes: Optional[dict] = None,
):
    """创建追踪 span。

    支持嵌套调用，自动管理父子关系。

    Args:
        name: Span 名称
        kind: Span 类型（INTERNAL/CLIENT/SERVER）
        attributes: Span 属性

    Yields:
        创建的 span 字典

    Example:
        ```python
        with traced_span("llm.call", attributes={"model": "gpt-4"}):
            # 执行 LLM 调用
            response = await llm.ainvoke(messages)
        ```
    """
    import uuid

    # 获取或创建上下文
    ctx = get_current_span_context()
    if ctx is None:
        ctx = SpanContext()
        set_span_context(ctx)

    # 创建新 span
    span_id = str(uuid.uuid4())
    start_time = time.time()

    span = {
        "name": name,
        "kind": kind,
        "span_id": span_id,
        "parent_span_id": ctx.current_span_id,
        "trace_id": ctx.trace_id or span_id,
        "start_time": start_time,
        "attributes": attributes or {},
        "depth": ctx.depth,
    }

    # 更新上下文
    ctx.spans.append(span)
    old_span_id = ctx.current_span_id
    ctx.current_span_id = span_id
    ctx.depth += 1

    if ctx.trace_id is None:
        ctx.trace_id = span_id

    try:
        yield span

    finally:
        # 记录结束时间
        span["end_time"] = time.time()
        span["duration_ms"] = (span["end_time"] - start_time) * 1000

        # 恢复父 span
        ctx.current_span_id = old_span_id
        ctx.depth -= 1

        # 发送到 Langfuse/LangSmith
        _export_span(span)


def _export_span(span: dict) -> None:
    """导出 span 到 tracing 后端。

    注意：Langfuse/LangSmith 的实际追踪由 LangChain CallbackHandler 自动处理。
    这里仅记录日志，不手动导出。

    Args:
        span: 要导出的 span 字典
    """
    # 仅记录调试日志
    logger.debug(
        f"Span completed: {span['name']} (duration: {span['duration_ms']:.2f}ms, "
        f"trace_id: {span['trace_id'][:12] if span.get('trace_id') else 'N/A'})"
    )

    # Langfuse/LangSmith 通过 LangChain CallbackHandler 自动追踪
    # 无需手动导出


