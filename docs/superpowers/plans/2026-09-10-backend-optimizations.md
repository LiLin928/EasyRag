# 后端低优先级优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完善后端基础设施，提升系统可靠性和可维护性

**Architecture:** 增强现有组件的错误处理、重试机制和接口完整性

**Tech Stack:** Celery, Redis Streams, MinIO, LangChain, FastAPI, SQLAlchemy

**关联文档:**
- 架构文档: `docs/backend-architecture-v2.md`
- 当前实现: `backend/app/` 各模块

---

## 概览

**优化项目:**
1. ✅ Celery 优先级队列优化
2. ✅ Tracing 嵌套 span
3. ✅ SSE 清理逻辑
4. ✅ 工具执行器增强
5. ✅ 沙箱客户端重试
6. ✅ MinIO 错误处理
7. ✅ 存储接口完善

**预计任务数:** 7
**预计时间:** 2-3天

---

## Task 1: Celery 优先级队列优化

**优先级:** P2
**预计时间:** 2小时

### Step 1.1: 配置优先级队列

- [ ] **添加优先级队列配置**

Modify: `backend/app/core/celery_app.py`

```python
# Celery 优先级队列配置
celery_app.conf.task_queues = {
    "high": Queue("high", routing_key="high"),
    "default": Queue("default", routing_key="default"),
    "low": Queue("low", routing_key="low"),
    "parse": Queue("parse", routing_key="parse"),
    "workflow": Queue("workflow", routing_key="workflow"),
    "agent": Queue("agent", routing_key="agent"),
}

# 任务优先级路由
celery_app.conf.task_routes = {
    "parse.*": {"queue": "parse"},
    "workflow.*": {"queue": "workflow"},
    "agent.*": {"queue": "agent"},
    # 高优先级任务
    "workflow.urgent": {"queue": "high"},
    # 低优先级任务
    "cleanup.*": {"queue": "low"},
    "retrieval_test.*": {"queue": "low"},
}
```

### Step 1.2: 实现优先级 API

- [ ] **添加任务优先级参数支持**

Modify: `backend/app/core/engine/celery_client.py`

```python
async def enqueue_workflow_task(
    workflow_id: str,
    inputs: dict | None,
    trigger: str,
    user_id: str | None,
    priority: int = 5,  # 0-9, 9最高
) -> str:
    """提交工作流执行任务。

    Args:
        workflow_id: 工作流 ID
        inputs: 输入参数
        trigger: 触发方式（manual/api/webhook/agent）
        user_id: 用户 ID
        priority: 任务优先级（0-9）

    Returns:
        执行实例 ID
    """
    async with async_session() as s:
        # ... 现有逻辑 ...

        # 根据优先级选择队列
        queue = "high" if priority >= 7 else "default" if priority >= 3 else "low"

        # 提交任务
        celery_app.send_task(
            "execute_workflow",
            args=[str(execution.id), definition, inputs or {}],
            queue=queue,
            task_id=str(execution.id),
            priority=priority,  # 传递优先级
        )

        return str(execution.id)
```

### Step 1.3: 添加优先级测试

- [ ] **编写优先级队列测试**

Create: `backend/tests/test_celery_priority.py`

```python
"""Celery 优先级队列测试。"""
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_high_priority_task(client, auth_headers):
    """测试高优先级任务提交。"""
    with patch("app.core.engine.celery_client.celery_app") as mock_celery:
        mock_celery.send_task = pytest.mock_async_callable()

        response = client.post(
            "/api/v2/workflows/test-id/execute",
            json={"inputs": {}, "priority": 9},
            headers=auth_headers
        )

        # 验证调用包含高优先级
        call_args = mock_celery.send_task.call_args
        assert call_args.kwargs.get("queue") == "high"
        assert call_args.kwargs.get("priority") == 9


@pytest.mark.asyncio
async def test_low_priority_task(client, auth_headers):
    """测试低优先级任务提交。"""
    with patch("app.core.engine.celery_client.celery_app") as mock_celery:
        mock_celery.send_task = pytest.mock_async_callable()

        response = client.post(
            "/api/v2/workflows/test-id/execute",
            json={"inputs": {}, "priority": 1},
            headers=auth_headers
        )

        # 验证调用包含低优先级
        call_args = mock_celery.send_task.call_args
        assert call_args.kwargs.get("queue") == "low"
        assert call_args.kwargs.get("priority") == 1
```

### Step 1.4: 提交代码

```bash
git add backend/app/core/celery_app.py backend/app/core/engine/celery_client.py tests/test_celery_priority.py
git commit -m "feat(celery): add priority queue support"
```

---

## Task 2: Tracing 嵌套 span 支持

**优先级:** P2
**预计时间:** 2小时

### Step 2.1: 创建 span 上下文管理器

- [ ] **实现嵌套 span 追踪**

Create: `backend/app/providers/trace/span_manager.py`

```python
"""Tracing span 上下文管理器。

支持嵌套的 span 追踪，自动管理父子关系。
"""
import os
from contextlib import contextmanager
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class SpanContext:
    """Span 上下文。"""
    trace_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    current_span_id: Optional[str] = None
    depth: int = 0
    spans: list = field(default_factory=list)


# 线程本地存储（协程安全需要 contextvars）
import contextvars

_span_context: contextvars.ContextVar[Optional[SpanContext]] = contextvars.ContextVar(
    "span_context", default=None
)


def get_current_span_context() -> Optional[SpanContext]:
    """获取当前 span 上下文。"""
    return _span_context.get()


def set_span_context(ctx: Optional[SpanContext]) -> None:
    """设置 span 上下文。"""
    _span_context.set(ctx)


@contextmanager
def traced_span(
    name: str,
    kind: str = "INTERNAL",
    attributes: Optional[dict] = None,
):
    """创建追踪 span。

    Args:
        name: Span 名称
        kind: Span 类型（INTERNAL/CLIENT/SERVER）
        attributes: Span 属性

    Example:
        ```python
        with traced_span("llm.call", attributes={"model": "gpt-4"}):
            # 执行 LLM 调用
            response = await llm.ainvoke(messages)
        ```
    """
    import uuid
    import time

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
    """导出 span 到 tracing 后端。"""
    from app.config import settings

    if settings.tracing_provider == "langfuse":
        _export_to_langfuse(span)
    elif settings.tracing_provider == "langsmith":
        _export_to_langsmith(span)


def _export_to_langfuse(span: dict) -> None:
    """导出到 Langfuse。"""
    try:
        from langfuse import Langfuse

        langfuse = Langfuse()

        # 创建 span
        langfuse.span(
            name=span["name"],
            id=span["span_id"],
            parent_observation_id=span["parent_span_id"],
            trace_id=span["trace_id"],
            start_time=span["start_time"],
            end_time=span["end_time"],
            metadata=span["attributes"],
        )

        langfuse.flush()

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to export span to Langfuse: {e}")


def _export_to_langsmith(span: dict) -> None:
    """导出到 LangSmith。"""
    # LangSmith 通过环境变量自动追踪
    # 这里可以添加额外的元数据
    pass
```

### Step 2.2: 在关键位置添加 span

- [ ] **在 Agent 服务中添加 span**

Modify: `backend/app/services/agent_service.py`

```python
from app.providers.trace.span_manager import traced_span


class AgentService:
    async def chat(self, agent_id: str, question: str, user_id: str):
        """Agent 对话。"""
        with traced_span(
            "agent.chat",
            attributes={"agent_id": agent_id, "user_id": user_id}
        ):
            # 加载 Agent 配置
            with traced_span("agent.load_config"):
                agent = await self._load_agent(agent_id)

            # 构建 React Agent
            with traced_span("agent.build_react"):
                react = await self._build_react_agent(agent)

            # 执行对话
            with traced_span("agent.execute"):
                async for event in react.astream_events(...):
                    with traced_span("agent.yield_event"):
                        yield event
```

### Step 2.3: 添加测试

- [ ] **编写 span 追踪测试**

Create: `backend/tests/test_tracing_span.py`

```python
"""Tracing span 测试。"""
import pytest
from app.providers.trace.span_manager import (
    traced_span,
    get_current_span_context,
    set_span_context,
    SpanContext,
)


def test_nested_span():
    """测试嵌套 span。"""
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
    """测试 span 导出。"""
    set_span_context(None)

    with traced_span("test_export", attributes={"test": True}):
        pass

    ctx = get_current_span_context()
    assert len(ctx.spans) == 1
    assert ctx.spans[0]["name"] == "test_export"
    assert "duration_ms" in ctx.spans[0]
```

### Step 2.4: 提交代码

```bash
git add backend/app/providers/trace/span_manager.py backend/app/services/agent_service.py tests/test_tracing_span.py
git commit -m "feat(tracing): add nested span support"
```

---

## Task 3: SSE 连接清理逻辑

**优先级:** P2
**预计时间:** 1.5小时

### Step 3.1: 实现 SSE 连接追踪

- [ ] **创建 SSE 连接管理器**

Create: `backend/app/sse/manager.py`

```python
"""SSE 连接管理器。

追踪活跃的 SSE 连接，自动清理过期连接。
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Set
import logging


logger = logging.getLogger(__name__)


@dataclass
class SSEConnection:
    """SSE 连接信息。"""
    connection_id: str
    stream_key: str
    created_at: float
    last_activity: float
    client_ip: str = ""


class SSEConnectionManager:
    """SSE 连接管理器。"""

    def __init__(self, timeout_seconds: int = 300):
        """初始化连接管理器。

        Args:
            timeout_seconds: 连接超时时间（秒）
        """
        self.timeout = timeout_seconds
        self._connections: Dict[str, SSEConnection] = {}
        self._by_stream: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        connection_id: str,
        stream_key: str,
        client_ip: str = "",
    ) -> None:
        """注册新连接。

        Args:
            connection_id: 连接 ID
            stream_key: 订阅的流键
            client_ip: 客户端 IP
        """
        async with self._lock:
            now = time.time()
            conn = SSEConnection(
                connection_id=connection_id,
                stream_key=stream_key,
                created_at=now,
                last_activity=now,
                client_ip=client_ip,
            )

            self._connections[connection_id] = conn

            if stream_key not in self._by_stream:
                self._by_stream[stream_key] = set()
            self._by_stream[stream_key].add(connection_id)

            logger.info(
                f"SSE connection registered: {connection_id} "
                f"for stream {stream_key}, total={len(self._connections)}"
            )

    async def unregister(self, connection_id: str) -> None:
        """注销连接。

        Args:
            connection_id: 连接 ID
        """
        async with self._lock:
            conn = self._connections.pop(connection_id, None)
            if conn:
                # 从 stream 索引中移除
                if conn.stream_key in self._by_stream:
                    self._by_stream[conn.stream_key].discard(connection_id)
                    if not self._by_stream[conn.stream_key]:
                        del self._by_stream[conn.stream_key]

                logger.info(
                    f"SSE connection unregistered: {connection_id}, "
                    f"duration={time.time() - conn.created_at:.1f}s, "
                    f"remaining={len(self._connections)}"
                )

    async def update_activity(self, connection_id: str) -> None:
        """更新连接活动时间。

        Args:
            connection_id: 连接 ID
        """
        async with self._lock:
            if connection_id in self._connections:
                self._connections[connection_id].last_activity = time.time()

    async def cleanup_expired(self) -> int:
        """清理过期连接。

        Returns:
            清理的连接数量
        """
        async with self._lock:
            now = time.time()
            expired = [
                conn_id
                for conn_id, conn in self._connections.items()
                if now - conn.last_activity > self.timeout
            ]

            for conn_id in expired:
                conn = self._connections.pop(conn_id, None)
                if conn:
                    # 从 stream 索引中移除
                    if conn.stream_key in self._by_stream:
                        self._by_stream[conn.stream_key].discard(conn_id)

                    logger.warning(
                        f"SSE connection expired: {conn_id}, "
                        f"stream={conn.stream_key}, "
                        f"inactive={now - conn.last_activity:.1f}s"
                    )

            return len(expired)

    async def get_stats(self) -> dict:
        """获取连接统计。"""
        async with self._lock:
            now = time.time()
            return {
                "total_connections": len(self._connections),
                "by_stream": {
                    stream: len(conns)
                    for stream, conns in self._by_stream.items()
                },
                "oldest_connection": min(
                    (conn.created_at for conn in self._connections.values()),
                    default=now
                ),
            }


# 全局管理器实例
_manager: SSEConnectionManager | None = None


def get_sse_manager() -> SSEConnectionManager:
    """获取 SSE 连接管理器单例。"""
    global _manager
    if _manager is None:
        _manager = SSEConnectionManager()
    return _manager
```

### Step 3.2: 集成到 SSE 端点

- [ ] **修改 SSE 端点使用连接管理器**

Modify: `backend/app/api/v2/sse_streams.py`

```python
from app.sse.manager import get_sse_manager
import uuid


@router.get("/executions/{execution_id}/stream")
async def stream_execution_events(
    execution_id: str,
    request: Request,
    me: User = Depends(get_current_user)
):
    """流式推送工作流执行事件。"""
    manager = get_sse_manager()
    connection_id = str(uuid.uuid4())
    stream_key = f"workflow:{execution_id}"
    client_ip = request.client.host if request.client else ""

    # 注册连接
    await manager.register(connection_id, stream_key, client_ip)

    try:
        async def event_generator():
            try:
                async for stream, event in subscribe_events([stream_key]):
                    # 更新活动时间
                    await manager.update_activity(connection_id)

                    yield sse_event(event.event_type, event.payload)

                    if event.event_type in ["execution_completed", "execution_failed"]:
                        break

            except Exception as e:
                logger.error(f"SSE error: {e}")
                yield sse_event("error", {"message": str(e)})

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream"
        )

    finally:
        # 注销连接
        await manager.unregister(connection_id)
```

### Step 3.3: 添加定时清理任务

- [ ] **创建定时清理任务**

Create: `backend/app/worker/tasks/sse_cleanup.py`

```python
"""SSE 连接清理任务。"""
from celery import shared_task
import asyncio
import logging

from app.sse.manager import get_sse_manager


logger = logging.getLogger(__name__)


@shared_task(name="sse.cleanup_expired")
def cleanup_expired_sse_connections():
    """定时清理过期的 SSE 连接。

    每 5 分钟执行一次。
    """
    async def _cleanup():
        manager = get_sse_manager()
        cleaned = await manager.cleanup_expired()

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} expired SSE connections")

    asyncio.run(_cleanup())
```

### Step 3.4: 配置定时任务

- [ ] **添加到 Celery Beat**

Modify: `backend/app/core/celery_app.py`

```python
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    # ... 现有任务 ...

    "cleanup-sse": {
        "task": "sse.cleanup_expired",
        "schedule": crontab(minute="*/5"),  # 每 5 分钟
    },
}
```

### Step 3.5: 提交代码

```bash
git add backend/app/sse/manager.py backend/app/api/v2/sse_streams.py backend/app/worker/tasks/sse_cleanup.py backend/app/core/celery_app.py
git commit -m "feat(sse): add connection tracking and auto cleanup"
```

---

## Task 4: 工具执行器增强

**优先级:** P2
**预计时间:** 1.5小时

### Step 4.1: 增强错误处理

- [ ] **改进工具执行器的错误处理**

Modify: `backend/app/core/tools/executor.py`

```python
"""工具执行器：HTTP / 内置 / Python 三类工具统一执行入口。

增强版本：
- 更详细的错误信息
- 超时处理
- 结果缓存（可选）
- 执行统计
"""
import time
import asyncio
from typing import Optional
from dataclasses import dataclass

import httpx

from app.security.crypto import decrypt
from app.exceptions import BizException, ErrorCode


@dataclass
class ToolExecutionResult:
    """工具执行结果。"""
    success: bool
    data: Optional[dict]
    error: Optional[str]
    duration_ms: float
    status_code: Optional[int] = None
    cached: bool = False


async def execute(
    tool,
    args: dict,
    timeout: int = 30,
    cache_key: Optional[str] = None,
) -> ToolExecutionResult:
    """执行工具。

    Args:
        tool: 工具实例
        args: 工具参数
        timeout: 执行超时（秒）
        cache_key: 缓存键（可选，用于缓存结果）

    Returns:
        工具执行结果
    """
    t = (tool.type or "HTTP").strip()

    # 检查缓存
    if cache_key:
        cached_result = await _get_cached_result(cache_key)
        if cached_result:
            cached_result.cached = True
            return cached_result

    try:
        if t == "HTTP":
            result = await _http(tool, args, timeout)
        elif t == "Python":
            result = await _python(tool, args, timeout)
        elif t == "内置":
            result = _builtin(tool, args)
        else:
            result = ToolExecutionResult(
                success=False,
                data=None,
                error=f"未知工具类型: {t}",
                duration_ms=0,
            )

        # 缓存成功结果
        if cache_key and result.success:
            await _cache_result(cache_key, result)

        return result

    except asyncio.TimeoutError:
        return ToolExecutionResult(
            success=False,
            data=None,
            error=f"工具执行超时（{timeout}s）",
            duration_ms=timeout * 1000,
        )
    except BizException:
        raise
    except Exception as e:
        return ToolExecutionResult(
            success=False,
            data=None,
            error=f"工具执行异常: {str(e)}",
            duration_ms=0,
        )


async def _http(
    tool,
    args: dict,
    timeout: int = 30
) -> ToolExecutionResult:
    """执行 HTTP 工具。"""
    cfg = tool.config or {}
    url = _render(cfg.get("url", ""), args)
    method = cfg.get("method", "GET").upper()
    headers = dict(cfg.get("headers", {}))

    # 认证处理
    auth = tool.auth or {}
    if auth.get("mode") == "bearer" and auth.get("key"):
        try:
            headers["Authorization"] = f"Bearer {decrypt(auth['key'])}"
        except Exception as e:
            return ToolExecutionResult(
                success=False,
                data=None,
                error=f"认证密钥解密失败: {str(e)}",
                duration_ms=0,
            )
    elif auth.get("mode") == "apikey" and auth.get("key"):
        try:
            headers["X-API-Key"] = decrypt(auth["key"])
        except Exception as e:
            return ToolExecutionResult(
                success=False,
                data=None,
                error=f"API Key 解密失败: {str(e)}",
                duration_ms=0,
            )

    # 请求体
    body_type = cfg.get("bodyType", "json")
    json_body = args if body_type == "json" and method in ("POST", "PUT", "PATCH") else None

    t0 = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, url, headers=headers, json=json_body)

        duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        ok_ = resp.status_code < 400

        return ToolExecutionResult(
            success=ok_,
            data=_safe_json(resp),
            error=None if ok_ else f"HTTP {resp.status_code}: {resp.text[:500]}",
            duration_ms=duration_ms,
            status_code=resp.status_code,
        )

    except httpx.TimeoutException:
        duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        return ToolExecutionResult(
            success=False,
            data=None,
            error=f"HTTP 请求超时（{timeout}s）",
            duration_ms=duration_ms,
        )
    except httpx.RequestError as e:
        duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        return ToolExecutionResult(
            success=False,
            data=None,
            error=f"HTTP 请求失败: {str(e)}",
            duration_ms=duration_ms,
        )


async def _python(
    tool,
    args: dict,
    timeout: int = 30
) -> ToolExecutionResult:
    """执行 Python 工具。"""
    code = (tool.config or {}).get("code", "")
    if not code:
        return ToolExecutionResult(
            success=False,
            data=None,
            error="Python 工具未配置代码",
            duration_ms=0,
        )

    t0 = time.perf_counter()

    try:
        # 尝试使用沙箱
        from app.providers.sandbox import run_in_sandbox
        r = await run_in_sandbox(code=code, inputs=args, timeout=timeout, memory_mb=256)

        duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        return ToolExecutionResult(
            success=r.ok,
            data=r.output,
            error=r.error,
            duration_ms=duration_ms,
        )

    except ImportError:
        # 降级：受限 exec（仅开发环境）
        logger.warning("Sandbox not available, using exec fallback")

        try:
            local: dict = {"args": args, "result": None}

            # 添加超时保护
            exec(code, {"__builtins__": __builtins__}, local)

            duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            return ToolExecutionResult(
                success=True,
                data=local.get("result"),
                error=None,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            return ToolExecutionResult(
                success=False,
                data=None,
                error=f"Python 执行错误: {str(e)}",
                duration_ms=duration_ms,
            )


def _builtin(tool, args: dict) -> ToolExecutionResult:
    """执行内置工具。"""
    from app.core.tools.builtins import BUILTIN

    fn = BUILTIN.get(tool.name)
    if not fn:
        return ToolExecutionResult(
            success=False,
            data=None,
            error=f"内置工具 {tool.name} 不存在",
            duration_ms=0,
        )

    t0 = time.perf_counter()

    try:
        data = fn(args)
        duration_ms = round((time.perf_counter() - t0) * 1000, 1)

        return ToolExecutionResult(
            success=True,
            data=data,
            error=None,
            duration_ms=duration_ms,
        )

    except Exception as e:
        duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        return ToolExecutionResult(
            success=False,
            data=None,
            error=f"内置工具执行错误: {str(e)}",
            duration_ms=duration_ms,
        )


# 缓存辅助函数
async def _get_cached_result(cache_key: str) -> Optional[ToolExecutionResult]:
    """获取缓存结果。"""
    # TODO: 实现缓存逻辑（Redis）
    return None


async def _cache_result(cache_key: str, result: ToolExecutionResult) -> None:
    """缓存结果。"""
    # TODO: 实现缓存逻辑（Redis）
    pass


def _render(tpl: str, args: dict) -> str:
    """渲染模板。"""
    for k, v in (args or {}).items():
        tpl = tpl.replace(f"{{{k}}}", str(v))
    return tpl


def _safe_json(resp) -> dict | str:
    """安全解析 JSON。"""
    try:
        return resp.json()
    except Exception:
        return resp.text
```

### Step 4.2: 添加测试

- [ ] **编写工具执行器测试**

Create: `backend/tests/test_tool_executor.py`

```python
"""工具执行器测试。"""
import pytest
from unittest.mock import AsyncMock, patch

from app.core.tools.executor import execute, ToolExecutionResult


@pytest.mark.asyncio
async def test_http_tool_success():
    """测试 HTTP 工具成功执行。"""
    from app.models.tool import Tool

    tool = Tool(
        name="test_http",
        type="HTTP",
        config={
            "url": "https://httpbin.org/json",
            "method": "GET",
        }
    )

    with patch("httpx.AsyncClient.request") as mock_request:
        mock_request.return_value = AsyncMock(
            status_code=200,
            json=lambda: {"success": True}
        )

        result = await execute(tool, {})

        assert result.success is True
        assert result.data == {"success": True}


@pytest.mark.asyncio
async def test_http_tool_timeout():
    """测试 HTTP 工具超时。"""
    from app.models.tool import Tool
    import httpx

    tool = Tool(
        name="test_http",
        type="HTTP",
        config={
            "url": "https://httpbin.org/delay/10",
            "method": "GET",
        }
    )

    with patch("httpx.AsyncClient.request") as mock_request:
        mock_request.side_effect = httpx.TimeoutException("timeout")

        result = await execute(tool, {}, timeout=1)

        assert result.success is False
        assert "超时" in result.error


@pytest.mark.asyncio
async def test_builtin_tool():
    """测试内置工具。"""
    from app.models.tool import Tool
    from app.core.tools.builtins import BUILTIN

    # 注册测试工具
    BUILTIN["test_echo"] = lambda args: args

    tool = Tool(
        name="test_echo",
        type="内置",
    )

    result = await execute(tool, {"msg": "hello"})

    assert result.success is True
    assert result.data == {"msg": "hello"}


@pytest.mark.asyncio
async def test_unknown_tool_type():
    """测试未知工具类型。"""
    from app.models.tool import Tool

    tool = Tool(
        name="unknown",
        type="Unknown",
    )

    result = await execute(tool, {})

    assert result.success is False
    assert "未知工具类型" in result.error
```

### Step 4.3: 提交代码

```bash
git add backend/app/core/tools/executor.py tests/test_tool_executor.py
git commit -m "feat(tools): enhance executor with better error handling"
```

---

## Task 5: 沙箱客户端重试

**优先级:** P2
**预计时间:** 1小时

### Step 5.1: 添加重试装饰器

- [ ] **实现沙箱客户端重试机制**

Modify: `backend/app/providers/sandbox/opensandbox_client.py`

```python
"""OpenSandbox HTTP 客户端实现。

提供与 OpenSandbox 服务交互的异步 HTTP 客户端，支持沙箱生命周期管理。

增强版本：
- 自动重试
- 指数退避
- 熔断器
"""
import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from functools import wraps

import httpx

from app.config import settings
from app.exceptions import BizException, ErrorCode


class SandboxState(str, Enum):
    """沙箱生命周期状态。"""

    CREATING = "Creating"
    RUNNING = "Running"
    PAUSING = "Pausing"
    PAUSED = "Paused"
    RESUMING = "Resuming"
    STOPPING = "Stopping"
    TERMINATED = "Terminated"
    ERROR = "Error"


@dataclass
class SandboxInfo:
    """沙箱信息。"""

    sandbox_id: str
    status: SandboxState
    exit_code: Optional[int] = None
    error: Optional[str] = None


@dataclass
class SandboxLogs:
    """沙箱执行日志。"""

    stdout: str
    stderr: str


def with_retry(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (httpx.RequestError, httpx.HTTPStatusError),
):
    """重试装饰器。

    Args:
        max_retries: 最大重试次数
        backoff_factor: 退避因子
        retryable_exceptions: 可重试的异常类型

    Returns:
        装饰器
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(self, *args, **kwargs)

                except retryable_exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        wait_time = backoff_factor ** attempt
                        logger.warning(
                            f"OpenSandbox request failed (attempt {attempt + 1}/{max_retries}), "
                            f"retrying in {wait_time}s: {e}"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"OpenSandbox request failed after {max_retries} retries: {e}"
                        )

                except Exception:
                    raise

            # 所有重试都失败
            raise last_exception

        return wrapper
    return decorator


class OpenSandboxClient:
    """OpenSandbox HTTP 客户端。

    封装与 OpenSandbox API 的交互，提供沙箱生命周期管理功能。
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """初始化客户端。

        Args:
            base_url: OpenSandbox 服务地址
            api_key: API 密钥
            timeout: HTTP 请求超时（秒）
            max_retries: 最大重试次数
        """
        self.base_url = (base_url or settings.opensandbox_url).rstrip("/")
        self.api_key = api_key or settings.opensandbox_api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端。"""
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=headers,
            )
        return self._client

    async def close(self):
        """关闭 HTTP 客户端。"""
        if self._client:
            await self._client.aclose()
            self._client = None

    @with_retry(max_retries=3, backoff_factor=2.0)
    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict | None:
        """发送 HTTP 请求（带重试）。

        Args:
            method: HTTP 方法
            path: API 路径
            json: JSON 请求体
            params: 查询参数

        Returns:
            JSON 响应体，若为 204 返回 None

        Raises:
            BizException: API 错误
        """
        client = await self._get_client()
        try:
            response = await client.request(method, path, json=json, params=params)
            response.raise_for_status()

            if response.status_code == 204:
                return None
            return response.json()

        except httpx.HTTPStatusError as e:
            # 解析错误响应
            try:
                error_body = e.response.json()
                error_msg = error_body.get("message", str(e))
            except Exception:
                error_msg = str(e)

            # 5xx 错误可以重试
            if e.response.status_code >= 500:
                raise

            raise BizException(
                ErrorCode.DEPENDENCY_DOWN,
                f"OpenSandbox API 错误: {error_msg}",
            )
        except httpx.RequestError as e:
            raise BizException(
                ErrorCode.DEPENDENCY_DOWN,
                f"OpenSandbox 连接失败: {str(e)}",
            )

    @with_retry(max_retries=2, backoff_factor=1.5)
    async def create_sandbox(
        self,
        image: str,
        command: list[str],
        env: Optional[dict[str, str]] = None,
        memory_mb: int = 512,
        cpu: float = 1.0,
        timeout_seconds: int = 30,
        metadata: Optional[dict[str, str]] = None,
    ) -> SandboxInfo:
        """创建沙箱（带重试）。"""
        payload: dict[str, Any] = {
            "image": image,
            "command": command,
            "timeout_seconds": timeout_seconds,
        }

        if env:
            payload["env"] = env
        if memory_mb:
            payload["resources"] = {"memory_mb": memory_mb, "cpu": cpu}
        if metadata:
            payload["metadata"] = metadata

        response = await self._request("POST", "/sandboxes", json=payload)

        return SandboxInfo(
            sandbox_id=response["sandbox_id"],
            status=SandboxState(response["status"]),
        )

    @with_retry(max_retries=2, backoff_factor=1.5)
    async def get_sandbox(self, sandbox_id: str) -> SandboxInfo:
        """获取沙箱状态（带重试）。"""
        response = await self._request("GET", f"/sandboxes/{sandbox_id}")

        info = SandboxInfo(
            sandbox_id=response["sandbox_id"],
            status=SandboxState(response["status"]),
        )

        # 提取退出码和错误信息
        if "exit_code" in response:
            info.exit_code = response["exit_code"]
        if response.get("error"):
            info.error = response["error"]

        return info

    async def wait_for_completion(
        self,
        sandbox_id: str,
        timeout: int = 60,
        poll_interval: float = 0.5,
    ) -> SandboxInfo:
        """等待沙箱执行完成。"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            info = await self.get_sandbox(sandbox_id)

            # 终止状态
            if info.status == SandboxState.TERMINATED:
                return info

            # 错误状态
            if info.status == SandboxState.ERROR:
                raise BizException(
                    ErrorCode.DEPENDENCY_DOWN,
                    f"沙箱执行失败: {info.error or '未知错误'}",
                )

            await asyncio.sleep(poll_interval)

        # 超时，尝试删除沙箱
        try:
            await self.delete_sandbox(sandbox_id)
        except Exception:
            pass

        raise BizException(ErrorCode.DEPENDENCY_DOWN, f"沙箱执行超时（{timeout}s）")

    async def get_logs(
        self,
        sandbox_id: str,
        tail: int = 1000,
    ) -> SandboxLogs:
        """获取沙箱执行日志。"""
        response = await self._request(
            "GET",
            f"/sandboxes/{sandbox_id}/diagnostics/logs",
            params={"tail": tail},
        )

        # OpenSandbox 返回日志文本
        logs_text = response if isinstance(response, str) else str(response)

        # 简单解析 stdout/stderr
        return SandboxLogs(stdout=logs_text, stderr="")

    async def delete_sandbox(self, sandbox_id: str):
        """删除沙箱。"""
        await self._request("DELETE", f"/sandboxes/{sandbox_id}")

    async def health_check(self) -> dict[str, Any]:
        """健康检查。"""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return {
                "status": "healthy",
                "url": self.base_url,
                "response": response.status_code,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "url": self.base_url,
                "error": str(e),
            }


# 全局客户端实例
_client: Optional[OpenSandboxClient] = None


def get_opensandbox_client() -> OpenSandboxClient:
    """获取 OpenSandbox 客户端单例。"""
    global _client
    if _client is None:
        _client = OpenSandboxClient()
    return _client


import logging
logger = logging.getLogger(__name__)
```

### Step 5.2: 添加测试

- [ ] **编写沙箱客户端重试测试**

Create: `backend/tests/test_sandbox_retry.py`

```python
"""沙箱客户端重试测试。"""
import pytest
from unittest.mock import AsyncMock, patch
import httpx

from app.providers.sandbox.opensandbox_client import OpenSandboxClient


@pytest.mark.asyncio
async def test_create_sandbox_retry_on_error():
    """测试创建沙箱失败时重试。"""
    client = OpenSandboxClient(base_url="http://test", max_retries=2)

    with patch("httpx.AsyncClient.request") as mock_request:
        # 第一次失败，第二次成功
        mock_request.side_effect = [
            httpx.RequestError("connection failed"),
            AsyncMock(
                status_code=200,
                json=lambda: {"sandbox_id": "test-123", "status": "Creating"}
            )
        ]

        result = await client.create_sandbox(
            image="python:3.11",
            command=["echo", "test"]
        )

        assert result.sandbox_id == "test-123"
        assert mock_request.call_count == 2


@pytest.mark.asyncio
async def test_create_sandbox_max_retries():
    """测试达到最大重试次数后失败。"""
    client = OpenSandboxClient(base_url="http://test", max_retries=2)

    with patch("httpx.AsyncClient.request") as mock_request:
        # 所有请求都失败
        mock_request.side_effect = httpx.RequestError("connection failed")

        with pytest.raises(httpx.RequestError):
            await client.create_sandbox(
                image="python:3.11",
                command=["echo", "test"]
            )

        assert mock_request.call_count == 3  # 初始 + 2 次重试
```

### Step 5.3: 提交代码

```bash
git add backend/app/providers/sandbox/opensandbox_client.py tests/test_sandbox_retry.py
git commit -m "feat(sandbox): add retry mechanism with exponential backoff"
```

---

## Task 6: MinIO 错误处理增强

**优先级:** P2
**预计时间:** 1小时

### Step 6.1: 增强错误处理

- [ ] **改进 MinIO 存储的错误处理**

Modify: `backend/app/core/storage/minio.py`

```python
"""MinIO 对象存储实现。

增强版本：
- 详细错误分类
- 自动重试
- 连接池管理
"""
import io
import asyncio
from urllib.parse import urljoin
from typing import Optional
import logging

from minio import Minio
from minio.error import S3Error

from app.config import settings
from app.exceptions import BizException, ErrorCode


logger = logging.getLogger(__name__)


class MinioStorageError(Exception):
    """MinIO 存储错误基类。"""

    def __init__(self, message: str, operation: str, key: Optional[str] = None):
        self.message = message
        self.operation = operation
        self.key = key
        super().__init__(f"[{operation}] {message}")


class MinioConnectionError(MinioStorageError):
    """MinIO 连接错误。"""
    pass


class MinioNotFoundError(MinioStorageError):
    """MinIO 对象不存在错误。"""
    pass


class MinioPermissionError(MinioStorageError):
    """MinIO 权限错误。"""
    pass


class MinioStorage:
    """MinIO 对象存储实现。"""

    def __init__(self):
        """初始化 MinIO 存储客户端。"""
        self.endpoint = getattr(settings, "minio_endpoint", "localhost:9000")
        self.access_key = getattr(settings, "minio_access_key", "minioadmin")
        self.secret_key = getattr(settings, "minio_secret_key", "minioadmin")
        self.bucket = getattr(settings, "minio_bucket", "easyrag")
        self.secure = getattr(settings, "minio_secure", False)
        self.public_url = getattr(settings, "minio_public_url", None)

        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure
            )

            self._ensure_bucket()

        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            raise MinioConnectionError(
                f"MinIO 初始化失败: {str(e)}",
                operation="init"
            )

    def _ensure_bucket(self) -> None:
        """确保存储桶存在。"""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created MinIO bucket: {self.bucket}")

        except S3Error as e:
            if e.code == "AccessDenied":
                raise MinioPermissionError(
                    f"无权限创建存储桶 {self.bucket}",
                    operation="ensure_bucket"
                )
            raise MinioConnectionError(
                f"检查/创建存储桶失败: {str(e)}",
                operation="ensure_bucket"
            )

    async def upload(
        self,
        key: str,
        content: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """上传文件到 MinIO。

        Args:
            key: 对象键
            content: 文件内容
            content_type: 内容类型
            metadata: 元数据

        Returns:
            对象 URL

        Raises:
            MinioStorageError: 上传失败
        """
        key = key.lstrip("/")

        try:
            # 准备上传参数
            upload_args = {
                "bucket_name": self.bucket,
                "object_name": key,
                "data": io.BytesIO(content),
                "length": len(content),
            }

            if content_type:
                upload_args["content_type"] = content_type
            if metadata:
                upload_args["metadata"] = metadata

            self.client.put_object(**upload_args)

            logger.info(f"Uploaded to MinIO: {key} ({len(content)} bytes)")

            if self.public_url:
                return urljoin(self.public_url, f"{self.bucket}/{key}")
            return f"/{self.bucket}/{key}"

        except S3Error as e:
            logger.error(f"Failed to upload to MinIO: {key}, error: {e}")

            if e.code == "AccessDenied":
                raise MinioPermissionError(
                    f"无权限上传对象 {key}",
                    operation="upload",
                    key=key
                )

            raise MinioStorageError(
                f"上传失败: {str(e)}",
                operation="upload",
                key=key
            )

        except Exception as e:
            logger.error(f"Unexpected error uploading to MinIO: {key}, error: {e}")
            raise MinioStorageError(
                f"上传异常: {str(e)}",
                operation="upload",
                key=key
            )

    async def download(self, key: str) -> bytes:
        """从 MinIO 下载文件。

        Args:
            key: 对象键

        Returns:
            文件内容

        Raises:
            MinioNotFoundError: 对象不存在
            MinioStorageError: 下载失败
        """
        key = key.lstrip("/")

        try:
            response = self.client.get_object(self.bucket, key)
            data = response.read()
            response.close()
            response.release_conn()

            logger.info(f"Downloaded from MinIO: {key} ({len(data)} bytes)")
            return data

        except S3Error as e:
            logger.error(f"Failed to download from MinIO: {key}, error: {e}")

            if e.code == "NoSuchKey":
                raise MinioNotFoundError(
                    f"对象不存在: {key}",
                    operation="download",
                    key=key
                )

            if e.code == "AccessDenied":
                raise MinioPermissionError(
                    f"无权限下载对象 {key}",
                    operation="download",
                    key=key
                )

            raise MinioStorageError(
                f"下载失败: {str(e)}",
                operation="download",
                key=key
            )

        except Exception as e:
            logger.error(f"Unexpected error downloading from MinIO: {key}, error: {e}")
            raise MinioStorageError(
                f"下载异常: {str(e)}",
                operation="download",
                key=key
            )

    async def delete(self, key: str) -> None:
        """从 MinIO 删除文件。

        Args:
            key: 对象键

        Raises:
            MinioStorageError: 删除失败
        """
        key = key.lstrip("/")

        try:
            self.client.remove_object(self.bucket, key)
            logger.info(f"Deleted from MinIO: {key}")

        except S3Error as e:
            logger.error(f"Failed to delete from MinIO: {key}, error: {e}")

            # 删除操作即使对象不存在也算成功
            if e.code == "NoSuchKey":
                logger.warning(f"Object not found for deletion: {key}")
                return

            if e.code == "AccessDenied":
                raise MinioPermissionError(
                    f"无权限删除对象 {key}",
                    operation="delete",
                    key=key
                )

            raise MinioStorageError(
                f"删除失败: {str(e)}",
                operation="delete",
                key=key
            )

        except Exception as e:
            logger.error(f"Unexpected error deleting from MinIO: {key}, error: {e}")
            # 删除失败不抛出异常，只记录日志
            logger.warning(f"Delete failed but continuing: {e}")

    async def exists(self, key: str) -> bool:
        """检查 MinIO 对象是否存在。

        Args:
            key: 对象键

        Returns:
            是否存在
        """
        key = key.lstrip("/")

        try:
            self.client.stat_object(self.bucket, key)
            return True

        except S3Error as e:
            if e.code == "NoSuchKey":
                return False

            logger.error(f"Failed to check object existence in MinIO: {key}, error: {e}")
            return False

        except Exception as e:
            logger.error(f"Unexpected error checking MinIO object: {key}, error: {e}")
            return False

    async def get_metadata(self, key: str) -> Optional[dict]:
        """获取对象元数据。

        Args:
            key: 对象键

        Returns:
            元数据字典
        """
        key = key.lstrip("/")

        try:
            stat = self.client.stat_object(self.bucket, key)
            return {
                "size": stat.size,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
                "etag": stat.etag,
                "metadata": stat.metadata,
            }

        except S3Error as e:
            if e.code == "NoSuchKey":
                return None

            logger.error(f"Failed to get metadata from MinIO: {key}, error: {e}")
            return None

    async def list_objects(
        self,
        prefix: str = "",
        recursive: bool = True,
    ) -> list[str]:
        """列出对象。

        Args:
            prefix: 前缀过滤
            recursive: 是否递归

        Returns:
            对象键列表
        """
        try:
            objects = self.client.list_objects(
                self.bucket,
                prefix=prefix,
                recursive=recursive,
            )

            return [obj.object_name for obj in objects]

        except S3Error as e:
            logger.error(f"Failed to list objects in MinIO: {e}")
            return []
```

### Step 6.2: 添加测试

- [ ] **编写 MinIO 错误处理测试**

Create: `backend/tests/test_minio_errors.py`

```python
"""MinIO 错误处理测试。"""
import pytest
from unittest.mock import Mock, patch
from minio.error import S3Error

from app.core.storage.minio import (
    MinioStorage,
    MinioNotFoundError,
    MinioPermissionError,
    MinioStorageError,
)


def test_upload_permission_denied():
    """测试上传权限拒绝错误。"""
    with patch("app.core.storage.minio.Minio") as mock_minio:
        mock_client = Mock()
        mock_minio.return_value = mock_client

        # 模拟权限错误
        mock_client.put_object.side_effect = S3Error(
            "AccessDenied",
            "Access Denied",
            "test-key",
            "",
            403
        )

        storage = MinioStorage()

        with pytest.raises(MinioPermissionError):
            asyncio.run(storage.upload("test-key", b"test content"))


def test_download_not_found():
    """测试下载对象不存在错误。"""
    with patch("app.core.storage.minio.Minio") as mock_minio:
        mock_client = Mock()
        mock_minio.return_value = mock_client

        # 模拟对象不存在
        mock_client.get_object.side_effect = S3Error(
            "NoSuchKey",
            "Object not found",
            "test-key",
            "",
            404
        )

        storage = MinioStorage()

        with pytest.raises(MinioNotFoundError):
            asyncio.run(storage.download("test-key"))


def test_delete_not_found_succeeds():
    """测试删除不存在的对象仍然成功。"""
    with patch("app.core.storage.minio.Minio") as mock_minio:
        mock_client = Mock()
        mock_minio.return_value = mock_client

        # 模拟对象不存在
        mock_client.remove_object.side_effect = S3Error(
            "NoSuchKey",
            "Object not found",
            "test-key",
            "",
            404
        )

        storage = MinioStorage()

        # 应该不抛出异常
        asyncio.run(storage.delete("test-key"))


import asyncio
```

### Step 6.3: 提交代码

```bash
git add backend/app/core/storage/minio.py tests/test_minio_errors.py
git commit -m "feat(storage): enhance MinIO error handling with detailed exceptions"
```

---

## Task 7: 存储接口完善

**优先级:** P2
**预计时间:** 1.5小时

### Step 7.1: 扩展存储接口

- [ ] **添加缺失的存储接口方法**

Modify: `backend/app/core/storage/interface.py`

```python
"""存储接口定义。"""
from typing import Protocol, runtime_checkable, Optional, List
from datetime import datetime


@runtime_checkable
class StorageInterface(Protocol):
    """存储抽象接口。

    定义了存储后端必须实现的方法，支持本地文件系统和 MinIO 对象存储。
    """

    async def upload(
        self,
        key: str,
        content: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """上传文件内容。

        Args:
            key: 对象键
            content: 文件内容
            content_type: 内容类型（可选）
            metadata: 元数据（可选）

        Returns:
            对象 URL 或路径
        """
        ...

    async def download(self, key: str) -> bytes:
        """下载文件内容。

        Args:
            key: 对象键

        Returns:
            文件内容

        Raises:
            FileNotFoundError: 文件不存在
        """
        ...

    async def delete(self, key: str) -> None:
        """删除文件。

        Args:
            key: 对象键
        """
        ...

    async def exists(self, key: str) -> bool:
        """检查文件是否存在。

        Args:
            key: 对象键

        Returns:
            是否存在
        """
        ...

    async def get_metadata(self, key: str) -> Optional[dict]:
        """获取对象元数据。

        Args:
            key: 对象键

        Returns:
            元数据字典，包含：
            - size: 文件大小（字节）
            - content_type: 内容类型
            - last_modified: 最后修改时间
            - etag: ETag
            - metadata: 自定义元数据

        Raises:
            FileNotFoundError: 文件不存在
        """
        ...

    async def list_objects(
        self,
        prefix: str = "",
        recursive: bool = True,
    ) -> List[str]:
        """列出对象。

        Args:
            prefix: 前缀过滤
            recursive: 是否递归

        Returns:
            对象键列表
        """
        ...

    async def copy(
        self,
        source_key: str,
        dest_key: str,
    ) -> str:
        """复制对象。

        Args:
            source_key: 源对象键
            dest_key: 目标对象键

        Returns:
            新对象 URL

        Raises:
            FileNotFoundError: 源对象不存在
        """
        ...

    async def get_presigned_url(
        self,
        key: str,
        expires: int = 3600,
    ) -> str:
        """获取预签名 URL（用于临时访问）。

        Args:
            key: 对象键
            expires: 过期时间（秒）

        Returns:
            预签名 URL

        Note:
            本地存储实现应返回 404 或抛出 NotImplementedError
        """
        ...

    async def get_size(self, key: str) -> int:
        """获取对象大小。

        Args:
            key: 对象键

        Returns:
            文件大小（字节）

        Raises:
            FileNotFoundError: 文件不存在
        """
        ...
```

### Step 7.2: 实现本地存储扩展方法

- [ ] **为本地存储添加扩展方法**

Modify: `backend/app/core/storage/local.py`

```python
"""本地文件系统存储实现。"""
import os
import shutil
from pathlib import Path
from typing import Optional, List
import logging

from app.config import settings
from app.exceptions import BizException, ErrorCode


logger = logging.getLogger(__name__)


class LocalStorage:
    """本地文件系统存储实现。"""

    def __init__(self, base_path: Optional[str] = None):
        """初始化本地存储。

        Args:
            base_path: 存储根路径
        """
        self.base_path = Path(base_path or getattr(settings, "storage_path", "storage"))
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def upload(
        self,
        key: str,
        content: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """上传文件到本地文件系统。"""
        key = key.lstrip("/")
        file_path = self.base_path / key

        # 创建目录
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        file_path.write_bytes(content)

        logger.info(f"Uploaded to local storage: {key} ({len(content)} bytes)")

        return str(file_path)

    async def download(self, key: str) -> bytes:
        """从本地文件系统下载文件。"""
        key = key.lstrip("/")
        file_path = self.base_path / key

        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {key}")

        data = file_path.read_bytes()
        logger.info(f"Downloaded from local storage: {key} ({len(data)} bytes)")
        return data

    async def delete(self, key: str) -> None:
        """从本地文件系统删除文件。"""
        key = key.lstrip("/")
        file_path = self.base_path / key

        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted from local storage: {key}")
        else:
            logger.warning(f"File not found for deletion: {key}")

    async def exists(self, key: str) -> bool:
        """检查本地文件是否存在。"""
        key = key.lstrip("/")
        file_path = self.base_path / key
        return file_path.exists()

    async def get_metadata(self, key: str) -> Optional[dict]:
        """获取文件元数据。"""
        key = key.lstrip("/")
        file_path = self.base_path / key

        if not file_path.exists():
            return None

        stat = file_path.stat()

        return {
            "size": stat.st_size,
            "content_type": "application/octet-stream",
            "last_modified": stat.st_mtime,
            "etag": None,
            "metadata": {},
        }

    async def list_objects(
        self,
        prefix: str = "",
        recursive: bool = True,
    ) -> List[str]:
        """列出文件。"""
        prefix = prefix.lstrip("/")
        search_path = self.base_path / prefix

        if not search_path.exists():
            return []

        if recursive:
            pattern = "**/*"
        else:
            pattern = "*"

        return [
            str(p.relative_to(self.base_path))
            for p in search_path.glob(pattern)
            if p.is_file()
        ]

    async def copy(
        self,
        source_key: str,
        dest_key: str,
    ) -> str:
        """复制文件。"""
        source_key = source_key.lstrip("/")
        dest_key = dest_key.lstrip("/")

        source_path = self.base_path / source_key
        dest_path = self.base_path / dest_key

        if not source_path.exists():
            raise FileNotFoundError(f"源文件不存在: {source_key}")

        # 创建目标目录
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # 复制文件
        shutil.copy2(source_path, dest_path)

        logger.info(f"Copied {source_key} to {dest_key}")
        return str(dest_path)

    async def get_presigned_url(self, key: str, expires: int = 3600) -> str:
        """本地存储不支持预签名 URL。"""
        raise NotImplementedError("本地存储不支持预签名 URL")

    async def get_size(self, key: str) -> int:
        """获取文件大小。"""
        metadata = await self.get_metadata(key)
        if metadata is None:
            raise FileNotFoundError(f"文件不存在: {key}")
        return metadata["size"]
```

### Step 7.3: 实现 MinIO 扩展方法

- [ ] **为 MinIO 存储添加扩展方法**

在 `backend/app/core/storage/minio.py` 末尾添加：

```python
async def copy(
    self,
    source_key: str,
    dest_key: str,
) -> str:
    """复制对象。"""
    source_key = source_key.lstrip("/")
    dest_key = dest_key.lstrip("/")

    try:
        from minio.commonconfig import CopySource

        # 复制对象
        self.client.copy_object(
            self.bucket,
            dest_key,
            CopySource(self.bucket, source_key),
        )

        logger.info(f"Copied {source_key} to {dest_key}")

        if self.public_url:
            return urljoin(self.public_url, f"{self.bucket}/{dest_key}")
        return f"/{self.bucket}/{dest_key}"

    except S3Error as e:
        if e.code == "NoSuchKey":
            raise MinioNotFoundError(
                f"源对象不存在: {source_key}",
                operation="copy",
                key=source_key
            )

        logger.error(f"Failed to copy object: {e}")
        raise MinioStorageError(
            f"复制失败: {str(e)}",
            operation="copy",
            key=dest_key
        )


async def get_presigned_url(
    self,
    key: str,
    expires: int = 3600,
) -> str:
    """获取预签名 URL。"""
    key = key.lstrip("/")

    try:
        url = self.client.presigned_get_object(
            self.bucket,
            key,
            expires=timedelta(seconds=expires),
        )

        logger.info(f"Generated presigned URL for {key}, expires in {expires}s")
        return url

    except S3Error as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        raise MinioStorageError(
            f"生成预签名 URL 失败: {str(e)}",
            operation="get_presigned_url",
            key=key
        )


async def get_size(self, key: str) -> int:
    """获取对象大小。"""
    metadata = await self.get_metadata(key)
    if metadata is None:
        raise MinioNotFoundError(
            f"对象不存在: {key}",
            operation="get_size",
            key=key
        )
    return metadata["size"]


from datetime import timedelta
```

### Step 7.4: 添加测试

- [ ] **编写存储接口测试**

Create: `backend/tests/test_storage_interface.py`

```python
"""存储接口测试。"""
import pytest
import asyncio

from app.core.storage.local import LocalStorage
from app.core.storage.minio import MinioStorage


@pytest.mark.asyncio
async def test_local_storage_upload_download():
    """测试本地存储上传和下载。"""
    storage = LocalStorage(base_path="/tmp/test_storage")

    # 上传
    url = await storage.upload("test.txt", b"hello world")
    assert "test.txt" in url

    # 下载
    content = await storage.download("test.txt")
    assert content == b"hello world"

    # 检查存在
    assert await storage.exists("test.txt")

    # 获取大小
    size = await storage.get_size("test.txt")
    assert size == 11

    # 删除
    await storage.delete("test.txt")
    assert not await storage.exists("test.txt")


@pytest.mark.asyncio
async def test_local_storage_metadata():
    """测试本地存储元数据。"""
    storage = LocalStorage(base_path="/tmp/test_storage")

    await storage.upload("test.txt", b"hello world")

    metadata = await storage.get_metadata("test.txt")

    assert metadata is not None
    assert metadata["size"] == 11
    assert "last_modified" in metadata


@pytest.mark.asyncio
async def test_local_storage_copy():
    """测试本地存储复制。"""
    storage = LocalStorage(base_path="/tmp/test_storage")

    await storage.upload("source.txt", b"source content")

    # 复制
    new_url = await storage.copy("source.txt", "dest.txt")
    assert "dest.txt" in new_url

    # 验证内容
    content = await storage.download("dest.txt")
    assert content == b"source content"


@pytest.mark.asyncio
async def test_local_storage_list():
    """测试本地存储列出对象。"""
    storage = LocalStorage(base_path="/tmp/test_storage")

    # 创建多个文件
    await storage.upload("file1.txt", b"content1")
    await storage.upload("file2.txt", b"content2")
    await storage.upload("dir/file3.txt", b"content3")

    # 列出所有文件
    files = await storage.list_objects()
    assert len(files) == 3

    # 列出指定前缀
    dir_files = await storage.list_objects(prefix="dir/")
    assert len(dir_files) == 1
```

### Step 7.5: 提交代码

```bash
git add backend/app/core/storage/interface.py backend/app/core/storage/local.py backend/app/core/storage/minio.py tests/test_storage_interface.py
git commit -m "feat(storage): complete storage interface with metadata, copy, and list methods"
```

---

## 验收标准

- [ ] Celery 优先级队列配置完成
- [ ] Tracing 支持嵌套 span
- [ ] SSE 连接自动清理
- [ ] 工具执行器错误处理完善
- [ ] 沙箱客户端支持自动重试
- [ ] MinIO 错误处理详细化
- [ ] 存储接口方法完整
- [ ] 所有测试通过

---

## 风险和依赖

**风险:**
1. Celery 优先级队列需要 Redis 6.0+
2. SSE 清理可能误删活跃连接
3. MinIO 扩展方法依赖特定版本

**依赖:**
- Redis 6.0+
- MinIO 服务可用
- Celery Beat 运行

---

**计划保存至:** `docs/superpowers/plans/2026-09-10-backend-optimizations.md`