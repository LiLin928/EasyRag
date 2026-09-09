# Phase 3 子项目 C：异步与扩展 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将工作流执行从 API 进程同步调用迁移到 ARQ worker 异步执行，SSE 事件从内存 Queue 迁移到 Redis Stream（支持跨进程 + 历史回放），统一 PostgresSaver checkpointer 单例支持断点恢复。

**Architecture:** API 进程只负责创建 execution 记录 + enqueue ARQ task + SSE 转发。ARQ worker 是唯一工作流执行者，通过 PostgresSaver checkpoint 支持断点恢复重试。Redis Stream 是 worker 和 API 之间的事件桥梁。Agent 调用工作流工具时 enqueue + 轮询 DB 等结果。

**Tech Stack:** ARQ (已有) + redis.asyncio (已有) + langgraph-checkpoint-postgres (已有) + pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-08-28-phase3-async-scalability-design.md`

## Global Constraints

- 前端契约不变：`/workflows/:id/execute` 返回 `{executionId, status}`，`/executions/:id/stream` 返回 SSE
- SSE 事件名不变：`execution_start` / `node_start` / `node_complete` / `execution_complete` / `execution_paused` / `error` / `execution_cancelled`
- Python 3.10 + FastAPI + SQLAlchemy 2.0 async + LangGraph + ARQ
- 统一响应：`ok(data)` → `{"code":0,"message":"success","data":...}`
- DB 会话：`from app.db.session import async_session`（async 上下文管理器）
- Redis 单例：`from app.db.redis import get_redis` → `redis.asyncio.Redis`（`decode_responses=True`）
- 测试模式：`@pytest.mark.asyncio` + `async def test_...`，conftest 每个 function 后 dispose engine

---

## File Structure

```
backend/app/
├── core/engine/
│   ├── arq_client.py          # Task 1: enqueue_workflow_task 工具函数
│   ├── sse_bus.py              # Task 2: 重写为 Redis Stream（publish + subscribe generator）
│   ├── graph_builder.py        # Task 3: 删除 _get_checkpointer，用 memory.get_checkpointer()
│   └── executor.py             # Task 4: _finish 保留为工具函数，execute_workflow/execuasync 删除
├── core/agent/
│   └── tool_registry.py        # Task 6: _workflow_tool 改为 enqueue + 轮询
├── worker/
│   └── app.py                  # Task 4: 新增 execute_workflow_task ARQ 任务
├── api/v2/
│   ├── workflows.py            # Task 5: execute 端点改 enqueue + 立即返回
│   └── executions.py           # Task 5: stream/resume/cancel 改造
└── core/agent/
    └── memory.py               # Task 3: worker startup 初始化钩子

backend/tests/
├── test_arq_client.py          # Task 1
├── test_sse_bus_redis.py       # Task 2
├── test_checkpointer_singleton.py  # Task 3
├── test_arq_workflow_task.py   # Task 4
├── test_workflow_executions_api.py  # Task 5
└── test_agent_workflow_polling.py   # Task 6
```

---

### Task 1: ARQ enqueue 工具函数

**Files:**
- Create: `app/core/engine/arq_client.py`
- Test: `tests/test_arq_client.py`

**Interfaces:**
- Consumes: `app.db.session.async_session`, `app.models.workflow.WorkflowExecution`, `app.config.settings.redis_url`
- Produces: `async def enqueue_workflow_task(workflow_id: str, inputs: dict | None, trigger: str, user_id: str | None) -> str` — 创建 execution 记录 + 入队 ARQ job，返回 execution_id

- [ ] **Step 1: Write the failing test**

```python
# tests/test_arq_client.py
"""ARQ enqueue 工具函数单元测试。"""
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_enqueue_creates_execution_and_job(monkeypatch):
    """enqueue_workflow_task 创建 WorkflowExecution 记录并入队 ARQ job。"""
    # Arrange: mock async_session 返回假 session
    fake_exec = type("E", (), {"id": "exec-123", "__dict__": {}})()
    fake_session_cm = AsyncMock()
    fake_session = AsyncMock()
    fake_session.add = lambda obj: setattr(obj, "id", "exec-123")
    fake_session.commit = AsyncMock()
    fake_session.refresh = AsyncMock()
    fake_session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.core.engine.arq_client.async_session", lambda: fake_session_cm)

    # Mock create_pool + enqueue_job
    fake_pool = AsyncMock()
    fake_pool.enqueue_job = AsyncMock()
    monkeypatch.setattr("app.core.engine.arq_client.create_pool", AsyncMock(return_value=fake_pool))

    from app.core.engine.arq_client import enqueue_workflow_task

    # Act
    result = await enqueue_workflow_task("wf-1", {"q": "hello"}, "manual", "user-1")

    # Assert
    assert result == "exec-123"
    fake_pool.enqueue_job.assert_called_once_with(
        "execute_workflow_task", execution_id="exec-123"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_arq_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.engine.arq_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/core/engine/arq_client.py
"""ARQ enqueue 工具函数：创建 execution 记录 + 入队 ARQ 任务。"""
from datetime import datetime

from arq import create_pool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import async_session
from app.models.workflow import Workflow, WorkflowExecution, WorkflowVersion


async def enqueue_workflow_task(
    workflow_id: str,
    inputs: dict | None,
    trigger: str,
    user_id: str | None,
) -> str:
    """创建 WorkflowExecution 记录并入队 ARQ 任务，返回 execution_id。

    API 进程和 Agent tool_registry 共用此函数。
    """
    # 1. 加载 workflow + version 获取 definition
    async with async_session() as s:
        wf = (
            await s.execute(select(Workflow).where(Workflow.id == workflow_id))
        ).scalar_one_or_none()
        if not wf:
            raise ValueError(f"工作流不存在: {workflow_id}")

        version = wf.current_version
        definition = wf.definition or {}
        if version > 0:
            ver = (
                await s.execute(
                    select(WorkflowVersion)
                    .where(WorkflowVersion.workflow_id == wf.id)
                    .where(WorkflowVersion.version == version)
                )
            ).scalar_one_or_none()
            if ver:
                definition = ver.definition_snapshot or definition

        # 2. 创建 execution 记录
        execution = WorkflowExecution(
            workflow_id=wf.id,
            version=version,
            user_id=user_id,
            status="running",
            trigger_type=trigger,
            inputs=inputs or {},
            started_at=datetime.now(),
        )
        s.add(execution)
        await s.commit()
        await s.refresh(execution)
        exec_id = str(execution.id)

    # 3. 入队 ARQ 任务
    pool = await create_pool(settings.redis_url)
    await pool.enqueue_job("execute_workflow_task", execution_id=exec_id)
    return exec_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_arq_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/engine/arq_client.py tests/test_arq_client.py
git commit -m "feat(phase3): ARQ enqueue helper for workflow execution"
```

---

### Task 2: Redis Stream SSE bus 重写

**Files:**
- Modify: `app/core/engine/sse_bus.py`（完全重写）
- Test: `tests/test_sse_bus_redis.py`

**Interfaces:**
- Consumes: `app.db.redis.get_redis` → `redis.asyncio.Redis`
- Produces:
  - `async def publish(execution_id: str, event: str, data: dict) -> None` — XADD 写入 Redis Stream
  - `async def subscribe(execution_id: str) -> AsyncGenerator[str, None]` — XRANGE 历史回放 + XREAD 实时尾随，yield SSE 格式字符串
  - 删除 `unsubscribe`、`drain`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sse_bus_redis.py
"""Redis Stream SSE bus 单元测试。"""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_publish_xadd_to_stream(monkeypatch):
    """publish 调用 XADD 写入 Redis Stream，key 为 execution:{eid}。"""
    fake_redis = AsyncMock()
    fake_redis.xadd = AsyncMock()
    monkeypatch.setattr("app.core.engine.sse_bus.get_redis", AsyncMock(return_value=fake_redis))

    from app.core.engine.sse_bus import publish

    await publish("exec-1", "node_start", {"nodeId": "llm_1"})

    fake_redis.xadd.assert_called_once()
    call_args = fake_redis.xadd.call_args
    assert call_args.args[0] == "execution:exec-1"
    assert call_args.kwargs.get("maxlen") == 500
    fields = call_args.args[1]
    assert fields["event"] == "node_start"
    assert json.loads(fields["data"])["nodeId"] == "llm_1"


@pytest.mark.asyncio
async def test_subscribe_yields_history_then_live(monkeypatch):
    """subscribe 先 XRANGE 读历史，再 XREAD 实时尾随，yield SSE 格式事件。"""
    fake_redis = AsyncMock()
    # XRANGE 返回两条历史事件
    fake_redis.xrange = AsyncMock(return_value=[
        ("0-1", {"event": "execution_start", "data": '{"total_nodes": 2}'}),
        ("0-2", {"event": "node_start", "data": '{"nodeId": "start"}'}),
    ])
    # XREAD 第一次返回一条实时事件，第二次返回 None（模拟流结束）
    xread_call_count = 0

    async def fake_xread(streams, block=None):
        nonlocal xread_call_count
        xread_call_count += 1
        if xread_call_count == 1:
            return {"execution:exec-1": [("0-3", {"event": "execution_complete", "data": '{"success": true}'})]}
        return None  # 模拟无更多事件

    fake_redis.xread = fake_xread
    monkeypatch.setattr("app.core.engine.sse_bus.get_redis", AsyncMock(return_value=fake_redis))

    from app.core.engine.sse_bus import subscribe

    events = []
    async for sse in subscribe("exec-1"):
        events.append(sse)
        if "execution_complete" in sse:
            break  # 终止事件后停止

    assert len(events) == 3
    assert "execution_start" in events[0]
    assert "node_start" in events[1]
    assert "execution_complete" in events[2]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sse_bus_redis.py -v`
Expected: FAIL — `publish` 仍写入内存 Queue，xadd 未被调用

- [ ] **Step 3: Write minimal implementation**

```python
# app/core/engine/sse_bus.py
"""SSE 事件总线：基于 Redis Stream 的工作流执行进度推送。

publish 写入 Redis Stream（XADD），subscribe 从 Stream 读取（XRANGE 历史回放 + XREAD 实时尾随）。
支持跨进程：ARQ worker publish，API 进程 subscribe。
"""
import asyncio
import json
from typing import AsyncGenerator

from app.db.redis import get_redis
from app.sse.emitter import sse_event

STREAM_KEY = "execution:{eid}"
MAXLEN = 500
# 终止事件名，subscribe 收到后停止读取
_TERMINAL_EVENTS = {"execution_complete", "error", "execution_cancelled", "execution_paused"}


async def publish(execution_id: str, event: str, data: dict) -> None:
    """向 Redis Stream 写入一条事件（XADD MAXLEN 500）。"""
    r = await get_redis()
    await r.xadd(
        STREAM_KEY.format(eid=execution_id),
        {"event": event, "data": json.dumps(data, ensure_ascii=False)},
        maxlen=MAXLEN,
    )


async def subscribe(execution_id: str) -> AsyncGenerator[str, None]:
    """订阅执行事件流：先 XRANGE 读历史，再 XREAD BLOCK 实时尾随。

    yield SSE 格式字符串。收到终止事件后停止。
    """
    r = await get_redis()
    key = STREAM_KEY.format(eid=execution_id)

    # 1. XRANGE 历史回放
    history = await r.xrange(key)
    for _id, fields in history:
        event = fields.get("event", "")
        data_raw = fields.get("data", "{}")
        try:
            data = json.loads(data_raw)
        except (json.JSONDecodeError, TypeError):
            data = {}
        yield sse_event(event, data)
        if event in _TERMINAL_EVENTS:
            return

    # 2. 记住最后一条 ID，从其后开始 XREAD
    last_id = history[-1][0] if history else "0-0"

    # 3. XREAD BLOCK 实时尾随
    while True:
        result = await r.xread({key: last_id}, block=0)
        if not result:
            continue
        for _key, messages in result:
            for msg_id, fields in messages:
                last_id = msg_id
                event = fields.get("event", "")
                data_raw = fields.get("data", "{}")
                try:
                    data = json.loads(data_raw)
                except (json.JSONDecodeError, TypeError):
                    data = {}
                yield sse_event(event, data)
                if event in _TERMINAL_EVENTS:
                    return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sse_bus_redis.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/engine/sse_bus.py tests/test_sse_bus_redis.py
git commit -m "feat(phase3): rewrite sse_bus to Redis Stream (XADD/XRANGE/XREAD)"
```

---

### Task 3: PostgresSaver checkpointer 单例统一

**Files:**
- Modify: `app/core/engine/graph_builder.py` — 删除 `_get_checkpointer`，改用 `app.core.agent.memory.get_checkpointer`
- Modify: `app/core/agent/memory.py` — 添加 worker startup 初始化钩子
- Test: `tests/test_checkpointer_singleton.py`

**Interfaces:**
- Consumes: `app.core.agent.memory.get_checkpointer` — 已有单例函数
- Produces: `graph_builder.GraphBuilder.build` 使用统一 checkpointer 单例

- [ ] **Step 1: Write the failing test**

```python
# tests/test_checkpointer_singleton.py
"""Checkpointer 单例统一测试。"""
from unittest.mock import patch, AsyncMock

import pytest


@pytest.mark.asyncio
async def test_graph_builder_uses_memory_singleton(monkeypatch):
    """GraphBuilder.build 调用 core.agent.memory.get_checkpointer 而非自建。"""
    fake_cp = AsyncMock()
    fake_cp.setup = AsyncMock()
    monkeypatch.setattr("app.core.agent.memory._checkpointer", fake_cp)
    monkeypatch.setattr("app.config.settings.env", "development")

    from app.core.engine.graph_builder import GraphBuilder
    from app.core.agent.memory import get_checkpointer

    builder = GraphBuilder()
    # 直接调 _get_checkpointer 应已删除 — 验证 AttributeError
    assert not hasattr(builder, "_get_checkpointer")
    # get_checkpointer 返回单例
    cp = await get_checkpointer()
    assert cp is fake_cp
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_checkpointer_singleton.py -v`
Expected: FAIL — `GraphBuilder` 仍有 `_get_checkpointer` 方法

- [ ] **Step 3: Write minimal implementation**

修改 `app/core/engine/graph_builder.py`：

```python
# app/core/engine/graph_builder.py（修改 build 方法的 checkpointer 部分）
"""GraphBuilder：workflow definition → LangGraph CompiledStateGraph。

1. 注册节点执行器（type → NodeRouter.create）
2. 注册边（普通 + 条件分支）
3. 入口（START → start node）/ 出口（end node → END）
4. checkpoint + 中断点（debug 暂停所有；human 暂停 human 节点前）
"""
from langgraph.graph import END, START, StateGraph

from app.core.agent.memory import get_checkpointer
from app.core.engine.nodes import basic  # noqa: F401 — 触发注册
from app.core.engine.nodes.base import NodeRouter
from app.core.engine.state import WorkflowState


class GraphBuilder:
    """将 workflow definition 编译为 LangGraph。"""

    async def build(self, definition: dict, execution_id: str, debug: bool = False):
        nodes = definition.get("nodes", [])
        edges = definition.get("edges", [])
        graph = StateGraph(WorkflowState)

        for nd in nodes:
            executor = NodeRouter.create(nd)
            graph.add_node(nd["id"], executor.run)

        for e in edges:
            src = e["source"]
            tgt = e["target"]
            handle = e.get("sourceHandle")
            if handle and handle not in ("output",):
                graph.add_conditional_edges(src, lambda s, h=handle: h, {handle: tgt})
            else:
                graph.add_edge(src, tgt)

        start_id = next((n["id"] for n in nodes if n["type"] == "start"), None)
        if start_id:
            graph.add_edge(START, start_id)

        for n in nodes:
            if n["type"] == "end":
                graph.add_edge(n["id"], END)

        checkpointer = await get_checkpointer()
        interrupt = ["*"] if debug else [
            n["id"] for n in nodes if n["type"] == "human"
        ]
        return graph.compile(checkpointer=checkpointer, interrupt_before=interrupt or None)
```

修改 `app/core/agent/memory.py` — 添加 worker startup 钩子：

```python
# app/core/agent/memory.py（在文件末尾追加）
async def init_checkpointer_for_worker():
    """ARQ worker startup 时提前初始化 checkpointer，避免首个任务冷启动。"""
    await get_checkpointer()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_checkpointer_singleton.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/engine/graph_builder.py app/core/agent/memory.py tests/test_checkpointer_singleton.py
git commit -m "feat(phase3): unify checkpointer singleton (graph_builder uses memory.get_checkpointer)"
```

---

### Task 4: ARQ 工作流任务 + executor 重构

**Files:**
- Modify: `app/worker/app.py` — 新增 `execute_workflow_task`，注册到 `WorkerSettings.functions`
- Modify: `app/core/engine/executor.py` — 删除 `execute_workflow` / `execute_workflow_sync`，保留 `_finish` 供 worker 调用
- Test: `tests/test_arq_workflow_task.py`

**Interfaces:**
- Consumes: Task 1 `enqueue_workflow_task`（间接，通过 execution_id）、Task 2 `sse_bus.publish`、Task 3 `get_checkpointer`、`GraphBuilder.build`
- Produces: `async def execute_workflow_task(ctx, execution_id: str)` — ARQ 任务函数，加载 execution + 构建 graph + astream + publish + cancel 检查

- [ ] **Step 1: Write the failing test**

```python
# tests/test_arq_workflow_task.py
"""ARQ 工作流任务单元测试。"""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_execute_workflow_task_fresh_run(monkeypatch):
    """无 checkpoint 时走全新执行（astream(initial)）。"""
    # Mock DB: 返回 execution + workflow + version
    fake_execution = MagicMock()
    fake_execution.id = "exec-1"
    fake_execution.workflow_id = "wf-1"
    fake_execution.version = 1
    fake_execution.inputs = {"q": "hello"}
    fake_execution.user_id = "user-1"
    fake_execution.status = "running"

    fake_wf = MagicMock()
    fake_wf.id = "wf-1"
    fake_wf.definition = {"nodes": [{"id": "start", "type": "start"}, {"id": "end", "type": "end"}], "edges": [{"source": "start", "target": "end"}]}
    fake_wf.current_version = 1

    fake_ver = MagicMock()
    fake_ver.definition_snapshot = fake_wf.definition

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=MagicMock(return_value=fake_execution)),  # execution
        MagicMock(scalar_one_or_none=MagicMock(return_value=fake_wf)),  # workflow
        MagicMock(scalar_one_or_none=MagicMock(return_value=fake_ver)),  # version
        MagicMock(scalar_one_or_none=MagicMock(return_value=fake_execution)),  # _is_cancelled
        MagicMock(scalar_one_or_none=MagicMock(return_value=fake_execution)),  # _finish
    ])
    fake_session.commit = AsyncMock()
    fake_session_cm = AsyncMock()
    fake_session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.worker.app.async_session", lambda: fake_session_cm)

    # Mock GraphBuilder.build → 返回 mock graph
    fake_graph = AsyncMock()
    fake_snapshot = MagicMock()
    fake_snapshot.next = None  # 无 checkpoint
    fake_graph.aget_state = AsyncMock(return_value=fake_snapshot)

    # astream 返回两轮事件
    async def fake_astream(initial, config=None, stream_mode=None):
        yield "start", {"node_outputs": {"start": {"output": "ok"}}, "status": "running"}
        yield "end", {"node_outputs": {"end": {"output": "done"}}, "status": "completed"}

    fake_graph.astream = fake_astream

    fake_builder = MagicMock()
    fake_builder.build = AsyncMock(return_value=fake_graph)
    monkeypatch.setattr("app.worker.app.GraphBuilder", lambda: fake_builder)

    # Mock sse_bus.publish
    mock_publish = AsyncMock()
    monkeypatch.setattr("app.worker.app.publish", mock_publish)

    from app.worker.app import execute_workflow_task

    # Act
    await execute_workflow_task(MagicMock(), "exec-1")

    # Assert: aget_state 被调用（检查 checkpoint）
    fake_graph.aget_state.assert_called_once()
    # publish 被调用（execution_start + node 事件 + execution_complete）
    assert mock_publish.call_count >= 3
    # publish 的第一个事件是 execution_start
    first_call = mock_publish.call_args_list[0]
    assert first_call.args[1] == "execution_start"


@pytest.mark.asyncio
async def test_execute_workflow_task_resume_from_checkpoint(monkeypatch):
    """有 checkpoint 时走断点恢复（astream(None)）。"""
    fake_execution = MagicMock()
    fake_execution.id = "exec-2"
    fake_execution.workflow_id = "wf-2"
    fake_execution.version = 1
    fake_execution.inputs = {"q": "resume"}
    fake_execution.user_id = "user-2"
    fake_execution.status = "running"

    fake_wf = MagicMock()
    fake_wf.id = "wf-2"
    fake_wf.definition = {"nodes": [{"id": "n1", "type": "start"}, {"id": "n2", "type": "end"}], "edges": [{"source": "n1", "target": "n2"}]}
    fake_wf.current_version = 1
    fake_ver = MagicMock()
    fake_ver.definition_snapshot = fake_wf.definition

    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=MagicMock(return_value=fake_execution)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=fake_wf)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=fake_ver)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=fake_execution)),  # _is_cancelled
        MagicMock(scalar_one_or_none=MagicMock(return_value=fake_execution)),  # _finish
    ])
    fake_session.commit = AsyncMock()
    fake_session_cm = AsyncMock()
    fake_session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.worker.app.async_session", lambda: fake_session_cm)

    fake_graph = AsyncMock()
    fake_snapshot = MagicMock()
    fake_snapshot.next = ("n2",)  # 有 checkpoint，下一个节点是 n2
    fake_graph.aget_state = AsyncMock(return_value=fake_snapshot)

    astream_input_received = []

    async def fake_astream(initial, config=None, stream_mode=None):
        astream_input_received.append(initial)
        yield "n2", {"node_outputs": {"n2": {"output": "resumed"}}, "status": "completed"}

    fake_graph.astream = fake_astream
    fake_builder = MagicMock()
    fake_builder.build = AsyncMock(return_value=fake_graph)
    monkeypatch.setattr("app.worker.app.GraphBuilder", lambda: fake_builder)
    monkeypatch.setattr("app.worker.app.publish", AsyncMock())

    from app.worker.app import execute_workflow_task

    await execute_workflow_task(MagicMock(), "exec-2")

    # Assert: astream 收到 None（断点恢复）
    assert astream_input_received[0] is None


@pytest.mark.asyncio
async def test_execute_workflow_task_cancel_detection(monkeypatch):
    """astream 循环检测到 DB status=cancelled 时 break。"""
    fake_execution = MagicMock()
    fake_execution.id = "exec-3"
    fake_execution.workflow_id = "wf-3"
    fake_execution.version = 1
    fake_execution.inputs = {}
    fake_execution.user_id = "user-3"
    fake_execution.status = "cancelled"  # 已被 cancel

    fake_wf = MagicMock()
    fake_wf.id = "wf-3"
    fake_wf.definition = {"nodes": [{"id": "s", "type": "start"}, {"id": "e", "type": "end"}], "edges": [{"source": "s", "target": "e"}]}
    fake_wf.current_version = 1
    fake_ver = MagicMock()
    fake_ver.definition_snapshot = fake_wf.definition

    call_count = 0

    async def fake_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            return MagicMock(scalar_one_or_none=MagicMock(return_value=fake_execution))
        return MagicMock(scalar_one_or_none=MagicMock(return_value=fake_execution))

    fake_session = AsyncMock()
    fake_session.execute = fake_execute
    fake_session.commit = AsyncMock()
    fake_session_cm = AsyncMock()
    fake_session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.worker.app.async_session", lambda: fake_session_cm)

    fake_graph = AsyncMock()
    fake_snapshot = MagicMock()
    fake_snapshot.next = None
    fake_graph.aget_state = AsyncMock(return_value=fake_snapshot)

    async def fake_astream(initial, config=None, stream_mode=None):
        yield "s", {"node_outputs": {"s": {}}, "status": "running"}
        # 下一轮 _is_cancelled 返回 True → 循环应中断

    fake_graph.astream = fake_astream
    fake_builder = MagicMock()
    fake_builder.build = AsyncMock(return_value=fake_graph)
    mock_publish = AsyncMock()
    monkeypatch.setattr("app.worker.app.publish", mock_publish)

    from app.worker.app import execute_workflow_task

    await execute_workflow_task(MagicMock(), "exec-3")

    # Assert: 发布了 execution_cancelled 事件
    cancel_calls = [c for c in mock_publish.call_args_list if c.args[1] == "execution_cancelled"]
    assert len(cancel_calls) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_arq_workflow_task.py -v`
Expected: FAIL — `execute_workflow_task` 不存在于 `worker/app.py`

- [ ] **Step 3: Write minimal implementation**

在 `app/worker/app.py` 添加 `execute_workflow_task` 并注册到 `WorkerSettings.functions`：

```python
# ===== 在 app/worker/app.py 顶部追加导入 =====
import time
from datetime import datetime

from sqlalchemy import select

from app.core.engine.graph_builder import GraphBuilder
from app.core.engine.sse_bus import publish
from app.models.workflow import WorkflowExecution, WorkflowVersion, Workflow


# ===== 在 app/worker/app.py 中追加任务函数 =====

async def execute_workflow_task(ctx, execution_id: str):
    """ARQ 任务：从 checkpoint 执行或恢复工作流。

    1. 从 DB 加载 execution + workflow definition
    2. 构建 graph（使用 PostgresSaver 单例 checkpointer）
    3. 检查 checkpoint：有 → astream(None) 断点恢复；无 → astream(initial) 全新执行
    4. astream 循环：每个节点完成 → publish 到 Redis Stream
    5. 每轮检查 DB status == "cancelled" → break
    6. 完成/失败/暂停 → 更新 DB + publish 最终事件
    """
    try:
        # 1. 加载 execution + workflow + version
        async with async_session() as s:
            execution = (
                await s.execute(
                    select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
                )
            ).scalar_one_or_none()
            if not execution:
                return

            wf = (
                await s.execute(select(Workflow).where(Workflow.id == execution.workflow_id))
            ).scalar_one_or_none()
            if not wf:
                await _finish_execution(execution_id, "failed", error="工作流不存在")
                await publish(execution_id, "error", {"message": "工作流不存在"})
                return

            version = wf.current_version
            definition = wf.definition or {}
            if version > 0:
                ver = (
                    await s.execute(
                        select(WorkflowVersion)
                        .where(WorkflowVersion.workflow_id == wf.id)
                        .where(WorkflowVersion.version == version)
                    )
                ).scalar_one_or_none()
                if ver:
                    definition = ver.definition_snapshot or definition

            exec_id = str(execution.id)
            wf_id = str(execution.workflow_id)
            user_id = str(execution.user_id) if execution.user_id else ""
            inputs = execution.inputs or {}
            debug = False

        # 2. 发布开始事件
        await publish(exec_id, "execution_start", {"total_nodes": len(definition.get("nodes", []))})

        # 3. 构建 graph
        builder = GraphBuilder()
        graph = await builder.build(definition, exec_id, debug)

        config = {"configurable": {"thread_id": exec_id}}

        # 4. 检查 checkpoint
        snapshot = await graph.aget_state(config)
        has_checkpoint = snapshot and snapshot.next

        initial = {
            "workflow_id": wf_id, "execution_id": exec_id, "thread_id": exec_id,
            "user_id": user_id, "variables": inputs,
            "node_outputs": {}, "status": "running", "started_at": time.time(),
            "node_timings": {}, "debug_mode": debug, "loop_stack": [],
        }

        stream_input = None if has_checkpoint else initial

        # 5. astream 循环
        t0 = time.perf_counter()
        try:
            async for ev in graph.astream(stream_input, config=config, stream_mode="updates"):
                for nid, update in ev.items():
                    if nid in ("__start__", "__end__"):
                        continue
                    await publish(exec_id, "node_start", {"nodeId": nid})
                    await publish(exec_id, "node_complete", {
                        "nodeId": nid,
                        "output": str(update.get("node_outputs", {}).get(nid, {}))[:500],
                    })
                    if update.get("status") == "paused":
                        await _finish_execution(exec_id, "paused")
                        await publish(exec_id, "execution_paused", {"nodeId": nid})
                        return
                # 每轮检查 cancel
                if await _is_cancelled(exec_id):
                    await _finish_execution(exec_id, "cancelled")
                    await publish(exec_id, "execution_cancelled", {"executionId": exec_id})
                    return
        except Exception as e:
            duration = round((time.perf_counter() - t0) * 1000, 1)
            await _finish_execution(exec_id, "failed", error=str(e), duration_ms=duration)
            await publish(exec_id, "error", {"message": str(e)})
            raise  # 让 ARQ 重试

        # 6. 完成
        duration = round((time.perf_counter() - t0) * 1000, 1)
        await _finish_execution(exec_id, "completed", duration_ms=duration)
        await publish(exec_id, "execution_complete", {"success": True, "duration_ms": duration})

    except Exception as e:
        await _finish_execution(execution_id, "failed", error=str(e))
        await publish(execution_id, "error", {"message": str(e)})
        raise


async def _is_cancelled(execution_id: str) -> bool:
    """检查 execution 是否被 cancel。"""
    async with async_session() as s:
        ex = (
            await s.execute(
                select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
            )
        ).scalar_one_or_none()
    return ex and ex.status == "cancelled"


async def _finish_execution(exec_id: str, status: str, error: str | None = None, duration_ms: float | None = None):
    """更新执行记录状态。"""
    async with async_session() as s:
        ex = (
            await s.execute(
                select(WorkflowExecution).where(WorkflowExecution.id == exec_id)
            )
        ).scalar_one_or_none()
        if ex:
            ex.status = status
            ex.error = error
            ex.duration_ms = duration_ms
            ex.completed_at = datetime.now() if status in ("completed", "failed", "cancelled") else None
            await s.commit()
```

更新 `WorkerSettings`：

```python
class WorkerSettings:
    """ARQ WorkerSettings。"""

    functions = [
        parse_document_task,
        reembed_chunks_task,
        run_retrieval_test_task,
        execute_workflow_task,   # Phase 3 新增
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    max_jobs = 4
    job_timeout = 600
    max_tries = 3
```

在 `startup` 钩子中添加 checkpointer 初始化：

```python
async def startup(ctx):
    """worker 启动钩子。"""
    ctx["ok"] = True
    # Phase 3: 提前初始化 checkpointer，避免首个任务冷启动
    from app.core.agent.memory import init_checkpointer_for_worker
    await init_checkpointer_for_worker()
```

清理 `app/core/engine/executor.py` — 删除 `execute_workflow` 和 `execute_workflow_sync`，保留 `_finish` 供兼容（或直接删除，因为 worker 自带 `_finish_execution`）：

```python
# app/core/engine/executor.py（清理后）
"""工作流执行入口（已迁移到 ARQ worker）。

原 execute_workflow / execute_workflow_sync 已移至 app.worker.app.execute_workflow_task。
本文件保留空模块以兼容潜在 import。
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_arq_workflow_task.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/worker/app.py app/core/engine/executor.py tests/test_arq_workflow_task.py
git commit -m "feat(phase3): ARQ workflow task with checkpoint resume + cancel detection"
```

---

### Task 5: API 端点改造

**Files:**
- Modify: `app/api/v2/workflows.py` — execute 端点改 enqueue + 立即返回
- Modify: `app/api/v2/executions.py` — stream 改 Redis Stream subscribe；resume 改 enqueue ARQ；cancel 改纯 DB
- Test: `tests/test_workflow_executions_api.py`

**Interfaces:**
- Consumes: Task 1 `enqueue_workflow_task`、Task 2 `sse_bus.subscribe`
- Produces: 改造后的 API 端点（前端契约不变）

- [ ] **Step 1: Write the failing test**

```python
# tests/test_workflow_executions_api.py
"""工作流执行 + 执行流 API 测试。"""
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_execute_endpoint_returns_immediately(monkeypatch):
 """POST /workflows/:id/execute 立即返回 executionId，不阻塞。"""
    monkeypatch.setattr("app.api.v2.workflows.enqueue_workflow_task", AsyncMock(return_value="exec-99"))

    # Mock workflow 存在 + 有定义
    fake_wf = type("W", (), {"id": "wf-1", "definition": {"nodes": [{"id": "s", "type": "start"}]}, "last_run": None, "__dict__": {}})()
    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=type("R", (), {"scalar_one_or_none": lambda self: fake_wf})())
    fake_session.commit = AsyncMock()
    fake_session.refresh = AsyncMock()
    fake_session_cm = AsyncMock()
    fake_session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.api.v2.workflows.async_session", lambda: fake_session_cm)

    from app.api.v2.workflows import execute
    from app.schemas.workflow import ExecuteRequest

    result = await execute("wf-1", ExecuteRequest(inputs={"q": "hi"}), me=type("U", (), {"id": "user-1"})())

    data = result.__dict__.get("body", b"")
    assert b"exec-99" in data or "exec-99" in str(result)


@pytest.mark.asyncio
async def test_stream_endpoint_uses_redis_subscribe(monkeypatch):
    """GET /executions/:id/stream 使用 sse_bus.subscribe（Redis Stream）。"""
    fake_execution = type("E", (), {"id": "e-1", "status": "running", "__dict__": {}})()
    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=type("R", (), {"scalar_one_or_none": lambda self: fake_execution})())
    fake_session_cm = AsyncMock()
    fake_session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.api.v2.executions.async_session", lambda: fake_session_cm)

    async def fake_subscribe(eid):
        yield 'event: execution_start\ndata: {"total_nodes": 1}\n\n'
        yield 'event: execution_complete\ndata: {"success": true}\n\n'

    monkeypatch.setattr("app.api.v2.executions.subscribe", fake_subscribe)

    from app.api.v2.executions import stream

    response = await stream("e-1", me=type("U", (), {"id": "u"})())

    # StreamingResponse 的 body_iterator 应产出事件
    assert response.media_type == "text/event-stream"


@pytest.mark.asyncio
async def test_resume_enqueues_arq(monkeypatch):
    """POST /executions/:id/resume 入队 ARQ task。"""
    fake_execution = type("E", (), {"id": "e-2", "status": "paused", "workflow_id": "wf-2", "inputs": {}, "__dict__": {}})()
    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=type("R", (), {"scalar_one_or_none": lambda self: fake_execution})())
    fake_session.commit = AsyncMock()
    fake_session_cm = AsyncMock()
    fake_session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.api.v2.executions.async_session", lambda: fake_session_cm)

    mock_enqueue = AsyncMock()
    monkeypatch.setattr("app.api.v2.executions.enqueue_workflow_task", mock_enqueue)

    from app.api.v2.executions import resume

    result = await resume("e-2", me=type("U", (), {"id": "u"})())
    mock_enqueue.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_only_updates_db(monkeypatch):
    """POST /executions/:id/cancel 只更新 DB status，不操作 sse_bus。"""
    fake_execution = type("E", (), {"id": "e-3", "status": "running", "__dict__": {}})()
    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=type("R", (), {"scalar_one_or_none": lambda self: fake_execution})())
    fake_session.commit = AsyncMock()
    fake_session_cm = AsyncMock()
    fake_session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.api.v2.executions.async_session", lambda: fake_session_cm)

    from app.api.v2.executions import cancel

    result = await cancel("e-3", me=type("U", (), {"id": "u"})())
    assert fake_execution.status == "cancelled"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_workflow_executions_api.py -v`
Expected: FAIL — execute 端点仍同步调用 `execute_workflow`

- [ ] **Step 3: Write minimal implementation**

修改 `app/api/v2/workflows.py` 的 execute 端点：

```python
# app/api/v2/workflows.py — execute 端点替换
@router.post("/{wid}/execute")
async def execute(wid: str, body: ExecuteRequest, me=Depends(get_current_user)):
    """触发工作流执行：创建 execution + 入队 ARQ task，立即返回 executionId。"""
    async with async_session() as s:
        wf = (await s.execute(select(Workflow).where(Workflow.id == wid))).scalar_one_or_none()
        if not wf:
            raise BizException(ErrorCode.NOT_FOUND, "工作流不存在")
        if not wf.definition or not wf.definition.get("nodes"):
            raise BizException(ErrorCode.BAD_REQUEST, "工作流定义为空，无法执行")

    from app.core.engine.arq_client import enqueue_workflow_task

    exec_id = await enqueue_workflow_task(wid, body.inputs or {}, "manual", str(me.id))

    async with async_session() as s:
        wf = (await s.execute(select(Workflow).where(Workflow.id == wid))).scalar_one_or_none()
        if wf:
            wf.last_run = datetime.now()
            await s.commit()

    return ok({"executionId": exec_id, "status": "running"})
```

修改 `app/api/v2/executions.py` — stream / resume / cancel：

```python
# app/api/v2/executions.py — stream 端点替换
@router.get("/{eid}/stream")
async def stream(eid: str, me=Depends(get_current_user)):
    """SSE 执行事件流：订阅 Redis Stream 实时推送执行进度。"""
    async with async_session() as s:
        ex = (
            await s.execute(select(WorkflowExecution).where(WorkflowExecution.id == eid))
        ).scalar_one_or_none()
        if not ex:
            raise BizException(ErrorCode.NOT_FOUND, "执行记录不存在")

    from app.core.engine.sse_bus import subscribe

    async def event_gen():
        try:
            # 如果执行已终态，推送最终状态后关闭
            if ex.status in ("completed", "failed", "cancelled"):
                from app.sse.emitter import sse_event
                yield sse_event("execution_complete", {"status": ex.status, "duration_ms": ex.duration_ms})
                return
            # 消费 Redis Stream 事件（XRANGE 历史 + XREAD 实时）
            async for event in subscribe(eid):
                yield event
        except asyncio.CancelledError:
            pass  # 客户端断开

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# app/api/v2/executions.py — resume 端点替换
@router.post("/{eid}/resume")
async def resume(eid: str, me=Depends(get_current_user)):
    """恢复暂停的执行：入队 ARQ task，worker 从 checkpoint 断点恢复。"""
    from app.core.engine.arq_client import enqueue_workflow_task
    from app.models.workflow import Workflow

    async with async_session() as s:
        ex = (
            await s.execute(select(WorkflowExecution).where(WorkflowExecution.id == eid))
        ).scalar_one_or_none()
        if not ex:
            raise BizException(ErrorCode.NOT_FOUND, "执行记录不存在")
        if ex.status != "paused":
            raise BizException(ErrorCode.BAD_REQUEST, "仅暂停状态的执行可恢复")
        ex.status = "running"
        await s.commit()
        wf_id = str(ex.workflow_id)
        inputs = ex.inputs or {}

    # 入队 ARQ task — worker 发现 checkpoint 存在 → astream(None) 断点恢复
    from arq import create_pool
    from app.config import settings
    pool = await create_pool(settings.redis_url)
    await pool.enqueue_job("execute_workflow_task", execution_id=eid)

    return ok({"success": True})


# app/api/v2/executions.py — cancel 端点替换
@router.post("/{eid}/cancel")
async def cancel(eid: str, me=Depends(get_current_user)):
    """取消执行：仅更新 DB status，worker astream 循环检测到后 break。"""
    from datetime import datetime

    async with async_session() as s:
        ex = (
            await s.execute(select(WorkflowExecution).where(WorkflowExecution.id == eid))
        ).scalar_one_or_none()
        if not ex:
            raise BizException(ErrorCode.NOT_FOUND, "执行记录不存在")
        if ex.status in ("completed", "failed", "cancelled"):
            raise BizException(ErrorCode.BAD_REQUEST, f"执行已{ex.status}，无法取消")
        ex.status = "cancelled"
        ex.completed_at = datetime.now()
        await s.commit()

    return ok({"success": True})
```

在 `executions.py` 顶部追加导入：

```python
from app.core.engine.arq_client import enqueue_workflow_task  # 用于 resume
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_workflow_executions_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/v2/workflows.py app/api/v2/executions.py tests/test_workflow_executions_api.py
git commit -m "feat(phase3): API endpoints use ARQ enqueue + Redis Stream SSE"
```

---

### Task 6: Agent 工具调用改造

**Files:**
- Modify: `app/core/agent/tool_registry.py` — `_workflow_tool` 改为 enqueue + 轮询
- Test: `tests/test_agent_workflow_polling.py`

**Interfaces:**
- Consumes: Task 1 `enqueue_workflow_task`、`app.db.session.async_session`（轮询 DB）
- Produces: 改造后的 `_workflow_tool` 返回 `StructuredTool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent_workflow_polling.py
"""Agent 工作流工具轮询测试。"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_workflow_tool_polls_until_completed(monkeypatch):
    """_workflow_tool 入队后轮询 DB，completed 时返回 outputs。"""
    from app.core.agent.tool_registry import _workflow_tool

    fake_wf = MagicMock()
    fake_wf.id = "wf-1"
    fake_wf.name = "my_workflow"
    fake_wf.description = "a test workflow"

    # Mock enqueue
    monkeypatch.setattr("app.core.agent.tool_registry.enqueue_workflow_task", AsyncMock(return_value="exec-1"))

    # Mock 轮询：第一次 running，第二次 completed
    call_count = 0

    class FakeExec:
        def __init__(self, status, outputs):
            self.status = status
            self.outputs = outputs

    async def fake_get_execution(eid):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return FakeExec("running", None)
        return FakeExec("completed", {"result": "done"})

    monkeypatch.setattr("app.core.agent.tool_registry._get_execution", fake_get_execution)
    monkeypatch.setattr("app.core.agent.tool_registry.asyncio.sleep", AsyncMock())

    tool = _workflow_tool(fake_wf)
    result = await tool.ainvoke({})

    assert result == '{"result": "done"}' or "done" in str(result)


@pytest.mark.asyncio
async def test_workflow_tool_timeout(monkeypatch):
    """轮询超时返回 '工作流执行超时'。"""
    from app.core.agent.tool_registry import _workflow_tool

    fake_wf = MagicMock()
    fake_wf.id = "wf-2"
    fake_wf.name = "slow_wf"
    fake_wf.description = ""

    monkeypatch.setattr("app.core.agent.tool_registry.enqueue_workflow_task", AsyncMock(return_value="exec-2"))

    class FakeExec:
        def __init__(self):
            self.status = "running"
            self.outputs = None

    monkeypatch.setattr("app.core.agent.tool_registry._get_execution", AsyncMock(return_value=FakeExec()))
    monkeypatch.setattr("app.core.agent.tool_registry.asyncio.sleep", AsyncMock())
    monkeypatch.setattr("app.core.agent.tool_registry.WORKFLOW_TIMEOUT_SECONDS", 3)

    tool = _workflow_tool(fake_wf)
    result = await tool.ainvoke({})

    assert "超时" in str(result)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_agent_workflow_polling.py -v`
Expected: FAIL — `_workflow_tool` 仍调用 `execute_workflow_sync`

- [ ] **Step 3: Write minimal implementation**

修改 `app/core/agent/tool_registry.py` 的 `_workflow_tool` 函数：

```python
# 在 tool_registry.py 顶部追加导入
import asyncio
import json

from app.core.engine.arq_client import enqueue_workflow_task
from app.db.session import async_session

WORKFLOW_TIMEOUT_SECONDS = 60


async def _get_execution(exec_id: str):
    """查询 execution 状态（供轮询使用）。"""
    from sqlalchemy import select
    from app.models.workflow import WorkflowExecution
    async with async_session() as s:
        return (
            await s.execute(
                select(WorkflowExecution).where(WorkflowExecution.id == exec_id)
            )
        ).scalar_one_or_none()


# 替换原有的 _workflow_tool 函数
def _workflow_tool(wf):
    async def _run(**kwargs) -> str:
        exec_id = await enqueue_workflow_task(
            str(wf.id), kwargs, trigger="agent", user_id=None
        )
        for _ in range(WORKFLOW_TIMEOUT_SECONDS):
            row = await _get_execution(exec_id)
            if row and row.status in ("completed", "failed", "cancelled"):
                if row.outputs:
                    return json.dumps(row.outputs, ensure_ascii=False)
                return f"工作流{row.status}"
            await asyncio.sleep(1)
        return "工作流执行超时"

    return StructuredTool.from_function(
        coroutine=_run,
        name=f"workflow_{wf.name}",
        description=wf.description or wf.name,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_agent_workflow_polling.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/agent/tool_registry.py tests/test_agent_workflow_polling.py
git commit -m "feat(phase3): agent workflow tool uses enqueue + DB polling"
```

---

## Plan 完成标志

- ✅ ARQ enqueue 工具函数（Task 1）
- ✅ Redis Stream SSE bus（Task 2）
- ✅ PostgresSaver checkpointer 单例统一（Task 3）
- ✅ ARQ 工作流任务 + executor 重构（Task 4）
- ✅ API 端点改造（Task 5）
- ✅ Agent 工具调用改造（Task 6）

## Self-Review

**1. Spec coverage:**
- §四 ARQ 工作流任务 → Task 1 (enqueue) + Task 4 (task function)
- §五 Redis Stream SSE → Task 2 (sse_bus) + Task 5 (stream endpoint)
- §六 PostgresSaver 单例 + 断点恢复 → Task 3 (singleton) + Task 4 (aget_state + astream(None))
- §六 Cancel 机制 → Task 4 (_is_cancelled) + Task 5 (cancel endpoint)
- §七 API 端点改造 → Task 5
- §八 Agent 工具调用 → Task 6
- §九 测试策略 → 每个 Task 内含 TDD 测试
- §十 文件变更清单 → 所有文件覆盖
- §十一 约束 → Global Constraints 声明

**2. Placeholder scan:** 无 TBD/TODO，所有步骤含实际代码。

**3. Type consistency:**
- `enqueue_workflow_task` 签名一致：(workflow_id, inputs, trigger, user_id) → str
- `publish` 签名一致：(execution_id, event, data) → None
- `subscribe` 签名一致：(execution_id) → AsyncGenerator[str, None]
- `_get_execution` 签名一致：(exec_id) → WorkflowExecution | None
- `WORKFLOW_TIMEOUT_SECONDS` 在 Task 6 中定义并使用

---

*— 计划结束 —*
