"""Tracing span 测试。

测试嵌套 span、span 导出等功能。
"""
import pytest
from app.providers.trace.span_manager import (
    traced_span,
    get_current_span_context,
    set_span_context,
    SpanContext,
)


def test_nested_span():
    """测试嵌套 span。

    验证：
    - 嵌套深度正确
    - 父子关系正确
    - 退出后深度恢复
    """
    set_span_context(None)

    with traced_span("parent", attributes={"level": 1}):
        ctx = get_current_span_context()
        assert ctx.depth == 1
        assert ctx.current_span_id is not None

        with traced_span("child", attributes={"level": 2}):
            ctx = get_current_span_context()
            assert ctx.depth == 2

            # 子 span 应该有父 span ID
            child_span = ctx.spans[-1]
            assert child_span["parent_span_id"] == ctx.spans[-2]["span_id"]

    # 退出后深度应该为 0
    ctx = get_current_span_context()
    assert ctx.depth == 0


def test_span_export():
    """测试 span 导出。

    验证：
    - span 正确创建
    - 持续时间被记录
    """
    set_span_context(None)

    with traced_span("test_export", attributes={"test": True}):
        pass

    ctx = get_current_span_context()
    assert len(ctx.spans) == 1
    assert ctx.spans[0]["name"] == "test_export"
    assert "duration_ms" in ctx.spans[0]


def test_multiple_siblings():
    """测试多个兄弟 span。

    验证：
    - 兄弟 span 有相同的父 span ID
    """
    set_span_context(None)

    with traced_span("parent"):
        with traced_span("child1"):
            pass
        with traced_span("child2"):
            pass

    ctx = get_current_span_context()
    assert len(ctx.spans) == 3
    # child1 和 child2 应该有相同的 parent_span_id
    assert ctx.spans[1]["parent_span_id"] == ctx.spans[2]["parent_span_id"]


def test_span_attributes():
    """测试 span 属性。

    验证：
    - 属性正确传递
    """
    set_span_context(None)

    attrs = {"model": "gpt-4", "temperature": 0.7, "max_tokens": 1000}
    with traced_span("llm.call", attributes=attrs):
        pass

    ctx = get_current_span_context()
    assert len(ctx.spans) == 1
    assert ctx.spans[0]["attributes"] == attrs


def test_trace_id_propagation():
    """测试 trace_id 传播。

    验证：
    - 所有 span 共享同一个 trace_id
    """
    set_span_context(None)

    with traced_span("root"):
        root_trace_id = get_current_span_context().trace_id

        with traced_span("child1"):
            ctx = get_current_span_context()
            assert ctx.trace_id == root_trace_id

            with traced_span("grandchild"):
                ctx = get_current_span_context()
                assert ctx.trace_id == root_trace_id

        with traced_span("child2"):
            ctx = get_current_span_context()
            assert ctx.trace_id == root_trace_id


def test_span_kind():
    """测试 span 类型。

    验证：
    - kind 参数正确设置
    """
    set_span_context(None)

    with traced_span("internal_op", kind="INTERNAL"):
        ctx = get_current_span_context()
        assert ctx.spans[-1]["kind"] == "INTERNAL"

    with traced_span("client_call", kind="CLIENT"):
        ctx = get_current_span_context()
        assert ctx.spans[-1]["kind"] == "CLIENT"


def test_deep_nesting():
    """测试深层嵌套。

    验证：
    - 多层嵌套时父子关系正确
    """
    set_span_context(None)

    with traced_span("level1"):
        ctx1 = get_current_span_context()
        span1 = ctx1.spans[-1]

        with traced_span("level2"):
            ctx2 = get_current_span_context()
            span2 = ctx2.spans[-1]
            assert span2["parent_span_id"] == span1["span_id"]

            with traced_span("level3"):
                ctx3 = get_current_span_context()
                span3 = ctx3.spans[-1]
                assert span3["parent_span_id"] == span2["span_id"]

                with traced_span("level4"):
                    ctx4 = get_current_span_context()
                    span4 = ctx4.spans[-1]
                    assert span4["parent_span_id"] == span3["span_id"]


def test_span_timing():
    """测试 span 时间记录。

    验证：
    - start_time 和 end_time 被记录
    - duration_ms 大于 0
    """
    import time

    set_span_context(None)

    with traced_span("timed_operation"):
        time.sleep(0.01)  # 10ms

    ctx = get_current_span_context()
    span = ctx.spans[0]
    assert "start_time" in span
    assert "end_time" in span
    assert "duration_ms" in span
    assert span["duration_ms"] > 0


def test_concurrent_contexts():
    """测试并发上下文隔离。

    验证：
    - 使用 contextvars 时，不同协程的上下文是隔离的
    """
    import asyncio

    async def task1():
        set_span_context(None)
        with traced_span("task1_span"):
            await asyncio.sleep(0.01)
            ctx = get_current_span_context()
            return len(ctx.spans)

    async def task2():
        set_span_context(None)
        with traced_span("task2_span"):
            await asyncio.sleep(0.01)
            ctx = get_current_span_context()
            return len(ctx.spans)

    async def run_concurrent():
        results = await asyncio.gather(task1(), task2())
        # 每个任务应该只有 1 个 span
        assert results[0] == 1
        assert results[1] == 1

    asyncio.run(run_concurrent())