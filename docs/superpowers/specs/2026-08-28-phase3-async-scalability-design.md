# Phase 3 子项目 C：异步与扩展 — 设计文档

> **日期**：2026-08-28
> **模块**：工作流异步执行 / Redis Stream SSE / PostgresSaver 持久化
> **状态**：已批准，待生成实施计划
>
> **实现状态**：全部 6 个 Task 已完成并测试通过（2026-08-28）
> **关联文档**：
> - `docs/backend-plans/后端设计方案-Phase2-3详细设计.md` §10（Phase 3 spec）
> - `docs/backend-plans/后端开发设计方案.md` 附录 E（实现进度）
> - `docs/superpowers/plans/2026-08-08-phase2-agents-and-phase3.md`（Plan 9 Phase 3 部分）

---

## 一、背景与范围

### 1.1 当前状态

Phase 2 已完成工作流引擎（LangGraph 12 节点 + SSE bus + checkpoint + 12 种执行器），但存在三个生产化瓶颈：

1. **工作流执行是同步的** — `POST /workflows/:id/execute` 在 API 进程中 `await execute_workflow()`，阻塞 HTTP 连接直到完成。长工作流会导致连接超时和 worker 阻塞。
2. **SSE bus 是纯内存的** — `sse_bus.py` 用 `asyncio.Queue` 字典实现，无法跨进程。多 worker 部署时事件丢失。
3. **Checkpointer 不是单例** — `GraphBuilder._get_checkpointer()` 每次构建图都创建新 PostgresSaver 实例；`core/agent/memory.py` 有单例但 graph_builder 不用它。Resume 端点用 `asyncio.create_task` 从头重跑而非断点恢复。

### 1.2 本文档范围

Phase 3 子项目 C，包含三项：

- **ARQ 工作流集成** — 工作流执行从 API 进程移到 ARQ worker，支持异步执行 + 断点恢复重试
- **Redis Stream SSE 多 worker 分发** — SSE 事件从内存 Queue 迁移到 Redis Stream，支持跨进程 + 历史回放
- **PostgresSaver checkpoint 持久化** — 统一 checkpointer 单例，生产环境持久化，支持断点恢复

### 1.3 不包含

- RBAC / 安全加固（子项目 A）
- MinIO 存储切换 / 运维（子项目 B）
- MinerU / 代码沙箱 / Webhook / 版本 diff（子项目 D）

---

## 二、关键决策

| # | 决策 | 选择 | 理由 |
|---|------|------|------|
| 1 | 工作流执行模式 | 全部走 ARQ，API 只入队 | 架构统一，不阻塞 HTTP 连接，Agent 轮询 DB 等结果 |
| 2 | SSE 事件投递 | Redis Streams（非 pub/sub） | 支持历史回放，客户端晚连接不丢事件，MAXLEN 自动清理 |
| 3 | 失败重试策略 | 断点恢复（PostgresSaver checkpoint） | 不重复执行已完成节点，避免副作用重复 |
| 4 | Cancel 机制 | DB 状态轮询 | 简单可靠，DB 是唯一真相源，延迟可接受（一个节点执行时间） |
| 5 | Checkpointer | 统一单例 | Agent 和工作流共享同一 PostgresSaver，避免连接池泄漏 |

---

## 三、整体架构

```
用户 POST /workflows/:id/execute
  → API 进程：创建 WorkflowExecution(status=running) → enqueue ARQ task → 返回 {executionId}

ARQ Worker (独立进程)
  → 拉取 task → 构建 LangGraph(PostgresSaver checkpointer 单例)
  → 检查 checkpoint：有 → astream(None) 断点恢复；无 → astream(initial) 全新执行
  → astream 循环：
      每个节点完成 → XADD 到 Redis Stream(execution:{eid})
      每轮检查 DB: if status == "cancelled" → break
  → 完成/失败/暂停 → 更新 DB + XADD 最终事件

用户 GET /executions/:id/stream
  → API 进程：XRANGE 从头读历史事件 → XREAD 实时尾随 → yield SSE
  → 客户端断开 → 生成器被 GC，自动停止 XREAD

Agent 调用工作流工具
  → enqueue ARQ task → 轮询 WorkflowExecution.status
  → status == completed → 读 execution.outputs 返回
  → status == failed → 返回错误
  → 超时(默认60s) → 返回"工作流执行超时"
```

核心变化：API 进程不再执行工作流，只负责入队和 SSE 转发。ARQ worker 是唯一执行者。Redis Stream 是 worker 和 API 之间的事件桥梁。

---

## 四、ARQ 工作流任务

### 4.1 任务函数

新增 `execute_workflow_task` 到 `worker/app.py` 的 `WorkerSettings.functions`：

```python
async def execute_workflow_task(ctx, execution_id: str):
    """ARQ 任务：从 checkpoint 执行或恢复工作流。"""
    # 1. 从 DB 加载 execution + workflow definition
    # 2. 构建 graph（使用 PostgresSaver 单例 checkpointer）
    # 3. 检查 checkpoint：
    #    snapshot = await graph.aget_state(config)
    #    has_checkpoint = snapshot and snapshot.next  # next 非空 = 有未完成节点
    #    - 有 → stream_input = None  # 断点恢复
    #    - 无 → stream_input = initial_state  # 全新执行
    # 4. astream 循环：
    #    - 每个节点完成 → XADD 到 Redis Stream
    #    - 每轮检查 DB status == "cancelled" → break
    # 5. 完成/失败/暂停 → 更新 DB + XADD 最终事件
```

### 4.2 ARQ 重试与断点恢复配合

ARQ `max_tries=3` 负责重试。第一次执行失败后，ARQ 重新入队同一个 task（相同 `execution_id`）。Task 函数检查 checkpoint：

- 已有 checkpoint（部分节点完成）→ `astream(None)` 从断点继续
- 无 checkpoint（连第一个节点都没跑完）→ `astream(initial)` 从头开始

LangGraph 的 PostgresSaver 在每个节点完成后保存 checkpoint。如果节点执行中途崩溃，该节点无 checkpoint，重试时会重新执行该节点。已完成的节点不会被重复执行。

### 4.3 ARQ enqueue 工具函数

新增 `core/engine/arq_client.py`：

```python
async def enqueue_workflow_task(workflow_id, inputs, trigger, user_id) -> str:
    """创建 execution 记录 + 入队 ARQ 任务，返回 execution_id。"""
    async with async_session() as s:
        exec = WorkflowExecution(
            workflow_id=workflow_id, status="running",
            trigger_type=trigger, inputs=inputs, started_at=datetime.now(),
        )
        s.add(exec); await s.commit(); await s.refresh(exec)
    pool = await create_pool(settings.redis_url)
    await pool.enqueue_job("execute_workflow_task", execution_id=str(exec.id))
    return str(exec.id)
```

API 进程和 Agent tool_registry 共用此函数。

---

## 五、Redis Stream SSE 投递

### 5.1 Stream 结构

```
Key:  execution:{eid}
写入: XADD execution:{eid} MAXLEN 500 * event "node_start" data '{"nodeId":"llm_1"}'
读取: XRANGE execution:{eid} - +              # 历史回放
      XREAD BLOCK 0 STREAMS execution:{eid} $  # 实时尾随
清理: MAXLEN 500 自动截断
```

工作流事件量小（几十条），500 条上限足够。工作流完成后 stream 可保留一段时间供回放，由定期清理任务删除（或 TTL）。

### 5.2 sse_bus.py 重写

接口保留 `publish` 名不变；`subscribe` 返回 async generator（取代 Queue），`unsubscribe` 删除（生成器关闭即取消订阅），`drain` 合并进 `subscribe` 生成器内部。调用方从 `async for event in drain(subscribe(eid))` 改为 `async for event in subscribe(eid)`。`publish` 签名不变，内部改为 `XADD`：

```python
# publish(execution_id, event, data) → XADD execution:{eid} MAXLEN 500 * event <name> data <json>
# subscribe(execution_id) → async generator: 先 XRANGE 读历史，再 XREAD BLOCK 0 实时尾随
# unsubscribe → 删除（生成器被 GC 或 break 即取消订阅）
# drain → 删除（合并进 subscribe 生成器内部）
```

调用方（`executor.py` 调 `publish`，`executions.py` 调 `subscribe`）需将 `drain(subscribe(...))` 改为直接 `async for event in subscribe(...)`。

### 5.3 SSE 端点改造

`GET /executions/:id/stream`：

```python
async def gen():
    # 1. XRANGE 读全部历史事件 → yield SSE
    # 2. XREAD BLOCK 0 实时尾随 → yield SSE
    # 3. 收到 execution_complete/error/cancelled → yield 后 break
    # 4. 客户端断开 → 生成器被 GC，自动停止 XREAD
```

不再使用内存 Queue 的 subscribe/unsubscribe。如果执行已完成（DB status 为终态），先推送最终状态事件后关闭。

---

## 六、PostgresSaver 单例 + 断点恢复

### 6.1 Checkpointer 统一

当前两个独立路径各自创建 checkpointer：

- `graph_builder.py._get_checkpointer()` — 每次构建图新建 PostgresSaver（连接池泄漏风险）
- `core/agent/memory.py.get_checkpointer()` — 有单例模式，但 graph_builder 不用它

改造：`graph_builder` 删除 `_get_checkpointer`，直接调用 `core/agent/memory.get_checkpointer()` 单例。Agent 和工作流共享同一 PostgresSaver 实例。ARQ worker 的 `startup` 钩子提前初始化。

### 6.2 断点恢复逻辑

```python
async def execute_workflow_task(ctx, execution_id: str):
    # ... 加载 execution + definition ...
    graph = await builder.build(definition, execution_id, debug)
    config = {"configurable": {"thread_id": execution_id}}

    snapshot = await graph.aget_state(config)
    has_checkpoint = snapshot and snapshot.next

    if has_checkpoint:
        stream_input = None        # 断点恢复
    else:
        stream_input = initial_state  # 全新执行

    async for ev in graph.astream(stream_input, config=config, stream_mode="updates"):
        for nid, update in ev.items():
            # ... 发布 Redis Stream 事件 ...
        if await _is_cancelled(execution_id):
            break
```

### 6.3 Cancel 机制

```
POST /executions/:id/cancel
  → DB: WorkflowExecution.status = "cancelled"
  → 不主动通知 worker（worker 自己查）

ARQ worker astream 循环:
  async for ev in graph.astream(...):
      # 处理节点事件...
      if await _is_cancelled(execution_id):   # 单条 SELECT，轻量
          await _finish(execution_id, "cancelled")
          await _xadd(execution_id, "execution_cancelled", {})
          break
```

Cancel 延迟 = 当前正在执行的节点完成时间。未来如需更强实时性可加 Redis pub/sub cancel 频道。

---

## 七、API 端点改造

### 7.1 Execute 端点（`workflows.py`）

不再同步执行，改为入队 + 立即返回：

```python
@router.post("/{wid}/execute")
async def execute(wid, body, me):
    # 1. 校验工作流存在 + 有定义
    # 2. enqueue_workflow_task(wid, body.inputs, "manual", me.id)
    # 3. 立即返回 ok({"executionId": exec_id, "status": "running"})
```

### 7.2 Resume 端点（`executions.py`）

真正的断点恢复，不再从头重跑：

```python
@router.post("/{eid}/resume")
async def resume(eid, me):
    # 1. 校验 status == "paused"
    # 2. status = "running"
    # 3. pool.enqueue_job("execute_workflow_task", execution_id=eid)
    # 4. Worker 发现 checkpoint 存在 → astream(None) 断点恢复
```

### 7.3 Cancel 端点（`executions.py`）

简化为纯 DB 操作：

```python
@router.post("/{eid}/cancel")
async def cancel(eid, me):
    # 1. status = "cancelled"
    # 2. 不再操作 sse_bus subscribe/unsubscribe
    # 3. Worker astream 循环检测到 cancelled → break
```

### 7.4 Stream 端点（`executions.py`）

Redis Stream 订阅，支持历史回放：

```python
@router.get("/{eid}/stream")
async def stream(eid, me):
    # 1. 校验 execution 存在
    # 2. 如果已终态 → 推送最终事件后关闭
    # 3. 否则 XRANGE 历史回放 + XREAD 实时尾随
```

---

## 八、Agent 工具调用改造

`core/agent/tool_registry.py` 的 `_workflow_tool` 从同步执行改为 enqueue + 轮询：

```python
def _workflow_tool(wf):
    async def _run(**kwargs) -> str:
        exec_id = await enqueue_workflow_task(str(wf.id), kwargs, trigger="agent")
        for _ in range(60):           # 60s 超时，可配置
            row = await _get_execution(exec_id)
            if row.status in ("completed", "failed", "cancelled"):
                return row.outputs or f"工作流{row.status}"
            await asyncio.sleep(1)
        return "工作流执行超时"
    return StructuredTool.from_function(coroutine=_run, ...)
```

Agent 调用工作流工具时，阻塞在轮询循环里等待 ARQ worker 完成。超时 60 秒可配置。Agent 的 ReAct 循环能拿到工作流结果后继续推理。

`execute_workflow_sync` 函数删除，由 `enqueue_workflow_task` + 轮询替代。

---

## 九、测试策略

| 层级 | 测试内容 | 策略 |
|------|---------|------|
| ARQ 任务单元测试 | `execute_workflow_task` 构建 graph、astream 循环、checkpoint 检测 | mock LangGraph `astream`，mock Redis `XADD`，验证调用序列 |
| Redis Stream SSE 单元测试 | `XRANGE` 历史回放 + `XREAD` 实时尾随 + 终止事件 | mock Redis client，验证 SSE 输出序列完整 |
| Cancel 单元测试 | DB flag 写入 + worker 循环检测 + break | mock DB 查询返回 cancelled，验证 astream 循环中断 |
| Checkpoint resume 单元测试 | 首次执行失败 → ARQ 重试 → `aget_state` 检测 → `astream(None)` | mock `aget_state` 返回有/无 checkpoint 两种场景 |
| Agent 轮询单元测试 | enqueue → 轮询 → 超时/完成/失败 | mock `enqueue_workflow_task` + mock DB 轮询，验证返回值 |
| 端到端集成测试 | execute → ARQ worker → Redis Stream → SSE → done | 需要 Redis + PostgreSQL 实例，标记 `@pytest.mark.integration` |

---

## 十、文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `core/engine/arq_client.py` | 新增 | `enqueue_workflow_task` 工具函数 |
| `worker/app.py` | 修改 | 新增 `execute_workflow_task` ARQ 任务 |
| `core/engine/executor.py` | 重构 | `execute_workflow` 变为 ARQ task 主体，移除同步调用路径，`execute_workflow_sync` 删除 |
| `core/engine/sse_bus.py` | 重写 | 内存 Queue → Redis Stream 读写，接口名 `publish`/`subscribe`/`drain` 不变 |
| `core/engine/graph_builder.py` | 修改 | `_get_checkpointer` 删除，改为调用 `core/agent/memory.get_checkpointer()` 单例 |
| `core/agent/memory.py` | 微调 | 确保 worker startup 时初始化 |
| `api/v2/workflows.py` | 修改 | execute 端点：enqueue + 立即返回 |
| `api/v2/executions.py` | 修改 | stream：Redis Stream 订阅；resume：enqueue ARQ；cancel：纯 DB |
| `core/agent/tool_registry.py` | 修改 | `_workflow_tool`：enqueue + 轮询等待 |
| `tests/test_arq_workflow.py` | 新增 | ARQ 任务 + checkpoint resume 测试 |
| `tests/test_redis_stream_sse.py` | 新增 | Redis Stream SSE 投递测试 |
| `tests/test_agent_workflow_polling.py` | 新增 | Agent 轮询集成测试 |

---

## 十一、约束

- **前端契约不变** — `/workflows/:id/execute` 仍返回 `{executionId, status}`，`/executions/:id/stream` 仍返回 SSE
- **SSE 事件名不变** — `execution_start` / `node_start` / `node_complete` / `execution_complete` / `execution_paused` / `error` / `execution_cancelled`
- **ARQ worker `WorkerSettings.functions` 新增** `execute_workflow_task`
- **`sse_bus.py` 接口变化** — `publish` 签名不变；`subscribe` 返回 async generator（取代 Queue）；`unsubscribe`/`drain` 删除。调用方从 `drain(subscribe(eid))` 改为 `async for event in subscribe(eid)`
- **技术栈** — `redis.asyncio`（已通过 ARQ 间接依赖）、`langgraph-checkpoint-postgres`（已在依赖中）

---

## 十二、实现进度

> 全部 6 个 Task 已按 TDD 流程完成，测试全部通过（13/13 PASS）。

| Task | 内容 | Commit | 测试文件 | 状态 |
|------|------|--------|----------|------|
| 1 | ARQ enqueue 工具函数 `enqueue_workflow_task` | `d66c6c7` | `tests/test_arq_client.py` (1 test) | 已完成 |
| 2 | Redis Stream SSE bus 重写 (`publish`/`subscribe`) | `5d74667` | `tests/test_sse_bus_redis.py` (2 tests) | 已完成 |
| 3 | PostgresSaver checkpointer 单例统一 | `91c54b6` | `tests/test_checkpointer_singleton.py` (1 test) | 已完成 |
| 4 | ARQ 工作流任务 + checkpoint resume + cancel 检测 | `ee3c859` | `tests/test_arq_workflow_task.py` (3 tests) | 已完成 |
| 5 | API 端点改造 (enqueue + Redis Stream SSE + DB cancel) | `3cb719d` | `tests/test_workflow_executions_api.py` (4 tests) | 已完成 |
| 6 | Agent 工具调用改造 (enqueue + DB 轮询 60s 超时) | `63be1ca` | `tests/test_agent_workflow_polling.py` (2 tests) | 已完成 |

### 额外修复

- **FastAPI 版本升级** 0.104.1 → 0.141.1 — 原安装版本与 Starlette 1.x 不兼容（`APIRouter.__init__` 传递 `on_startup`/`on_shutdown` 已被移除），导致 Task 5 测试无法 import API 路由模块。升级后根因消除。
- **`ExecuteRequest` schema 补字段** — `app/schemas/workflow.py` 的 `ExecuteRequest` 缺少 `inputs` 字段，而 `execute` 端点使用 `body.inputs`。已添加 `inputs: dict | None = None`。

### 关键实现细节确认

- SSE bus 接口：`publish(execution_id, event, data)` → XADD MAXLEN 500；`subscribe(execution_id)` → XRANGE + XREAD BLOCK 0 async generator
- `enqueue_workflow_task(workflow_id, inputs, trigger, user_id) -> str` — API 和 Agent 共用
- `execute_workflow_task(ctx, execution_id)` — ARQ worker 唯一执行入口
- Cancel 机制：API 仅更新 DB `status="cancelled"`，worker `_is_cancelled` 轮询检测后 break
- Resume：`create_pool` + `enqueue_job("execute_workflow_task", execution_id=eid)`，worker `aget_state` 检测 checkpoint → `astream(None)` 断点恢复
- Agent `_workflow_tool`：`enqueue_workflow_task` + 1s 间隔轮询 `_get_execution`，60s 超时

---

## 文档版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| V1.0 | 2026-08-28 | Phase 3 子项目 C 设计方案：ARQ 工作流集成 + Redis Stream SSE + PostgresSaver 持久化 |
| V1.1 | 2026-08-28 | 全部 6 个 Task 实现完成，添加实现进度章节；FastAPI 升级 0.141.1 |

---

*— 文档结束 —*
