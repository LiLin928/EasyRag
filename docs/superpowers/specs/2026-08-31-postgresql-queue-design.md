# Phase 4: PostgreSQL 持久化工作流队列 — 设计文档

> **日期**：2026-08-31
> **模块**：工作流执行 / PostgreSQL 队列 / SSE 事件流
> **状态**：已批准，待生成实施计划
>
> **目标**：将工作流执行从 Redis ARQ 迁移到 PostgreSQL 持久化队列，解决 Redis 重启数据丢失问题
>
> **关联文档**：
> - `docs/superpowers/specs/2026-08-28-phase3-async-scalability-design.md`（Phase 3 原始设计）
> - `docs/backend-plans/后端设计方案-Phase2-3详细设计.md`

---

## 一、背景与动机

### 1.1 当前架构问题

Phase 3 已完成的工作流引擎使用 **Redis ARQ + Redis Stream** 实现：
- **ARQ 队列**：任务存储在 Redis List，Redis 重启导致任务丢失
- **Redis Stream**：SSE 事件流存储在内存，Redis 重启导致执行进度丢失
- **单例连接**：`_redis` 全局单例，Redis 重启后连接不自动恢复

### 1.2 目标

将工作流执行完全迁移到 **PostgreSQL 持久化存储**：
1. 任务队列 → `job_queue` 表（持久化、可恢复）
2. 事件流 → `execution_events` 表（历史可查、断点恢复）
3. Worker 触发 → 混合轮询（自适应频率）
4. SSE 推送 → API 轮询 DB + 实时推送

### 1.3 不包含

- LangGraph 引擎逻辑（保持不变）
- Checkpoint 机制（PostgresSaver 已持久化）
- 前端契约（API 接口保持不变）

---

## 二、关键决策

| # | 决策 | 选择 | 理由 |
|---|------|------|------|
| 1 | 任务队列存储 | PostgreSQL `job_queue` 表 | 天然持久化，ACID 保证，无需额外组件 |
| 2 | Worker 触发机制 | 混合轮询（100ms → 5000ms） | 简单可靠，无外部依赖，自适应负载 |
| 3 | 事件流存储 | PostgreSQL `execution_events` 表 | 与执行状态统一存储，支持历史查询 |
| 4 | SSE 实时推送 | API 轮询 DB（500ms）→ SSE | 保持前端契约，实现简单，延迟可接受 |
| 5 | Worker 部署模式 | 多进程独立 Worker | 与 API 分离，可独立扩缩容 |
| 6 | 任务出队原子性 | `SELECT ... FOR UPDATE SKIP LOCKED` | 多 Worker 并发安全，无重复执行 |
| 7 | 断点恢复 | 复用 PostgresSaver checkpoint | 执行状态已持久化，Worker 重启可恢复 |

---

## 三、整体架构

```
用户 POST /workflows/:id/execute
  → API 进程：
      INSERT WorkflowExecution(status='running')
      INSERT job_queue(status='pending', execution_id=...)
      RETURN {executionId}

Worker 进程（独立部署，多实例）
  → 混合轮询：
      有任务：100ms 间隔快速处理
      无任务：5000ms 间隔节能
  → 出队：SELECT ... FOR UPDATE SKIP LOCKED
          UPDATE job_queue SET status='running'
  → 构建 LangGraph(PostgresSaver)
  → 检查 checkpoint：
      有 → astream(None) 断点恢复
      无 → astream(initial) 全新执行
  → astream 循环：
      每个节点完成 → INSERT execution_events
                     UPDATE WorkflowExecution
      每轮检查 DB: if status == 'cancelled' → break
  → 完成 → UPDATE job_queue SET status='completed'
           INSERT execution_events(event='execution_complete')

用户 GET /executions/:id/stream (SSE)
  → API 进程：
      SELECT * FROM execution_events WHERE execution_id = :eid ORDER BY seq
      yield 历史事件
      LOOP（每 500ms）：
          SELECT * FROM execution_events WHERE seq > :last_seq
          yield 新事件
          if event in ('execution_complete', 'error', 'cancelled'):
              break
      → 客户端断开 → 清理资源

Agent 调用工作流工具
  → pg_queue.enqueue(...) → RETURN execution_id
  → 轮询 WorkflowExecution.status（1s 间隔，60s 超时）
  → status == 'completed' → 读 execution.outputs
  → status == 'failed' → 返回错误
```

### 核心变化

| 组件 | 改造前 | 改造后 |
|------|--------|--------|
| 任务队列 | Redis ARQ List | PostgreSQL `job_queue` 表 |
| Worker 触发 | Redis 通知 | 混合轮询 |
| 事件流 | Redis Stream | PostgreSQL `execution_events` 表 |
| SSE 订阅 | Redis XREAD | DB SELECT + 轮询 |
| 持久化 | 内存 + 部分 DB | 完全 PostgreSQL |

---

## 四、数据库设计

### 4.1 job_queue 表

```sql
CREATE TABLE job_queue (
    id BIGSERIAL PRIMARY KEY,
    execution_id UUID NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
        -- pending: 等待执行
        -- running: 正在执行
        -- completed: 成功完成
        -- failed: 执行失败
        -- cancelled: 已取消
    worker_id VARCHAR(100),
    priority INT DEFAULT 0,  -- 优先级，高优先先执行
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    error_msg TEXT,
    timeout_seconds INT DEFAULT 600  -- 任务超时时间
);

CREATE INDEX idx_job_queue_status_priority 
ON job_queue(status, priority DESC, created_at ASC);

CREATE INDEX idx_job_queue_worker 
ON job_queue(worker_id) WHERE status = 'running';
```

### 4.2 execution_events 表

```sql
CREATE TABLE execution_events (
    seq BIGSERIAL PRIMARY KEY,
    execution_id UUID NOT NULL,
    event_type VARCHAR(50) NOT NULL,
        -- execution_start: 执行开始
        -- node_start: 节点开始
        -- node_complete: 节点完成
        -- execution_complete: 执行完成
        -- execution_paused: 执行暂停
        -- execution_cancelled: 执行取消
        -- error: 错误
    data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_exec_seq 
ON execution_events(execution_id, seq);

CREATE INDEX idx_events_exec_time 
ON execution_events(execution_id, created_at);
```

### 4.3 数据一致性

- **外键约束**：`job_queue.execution_id` → `WorkflowExecution.id`
- **事务边界**：enqueue/dequeue/事件插入均为独立事务，失败可重试
- **清理策略**：completed/failed 任务保留 7 天，由定时任务清理

---

## 五、核心模块设计

### 5.1 pg_queue.py - PostgreSQL 队列客户端

**职责**：任务入队、出队、状态管理

```python
# 核心接口
class PGJobQueue:
    async def enqueue(
        self,
        workflow_id: str,
        inputs: dict,
        trigger: str,
        user_id: str,
        priority: int = 0
    ) -> str: ...  # 返回 execution_id

    async def dequeue(self, worker_id: str) -> dict | None: ...
        # SELECT ... FOR UPDATE SKIP LOCKED
        # 返回 {execution_id, inputs, ...} 或 None

    async def complete(self, execution_id: str, status: str, error: str = None): ...
        # UPDATE job_queue SET status=..., completed_at=NOW()

    async def cancel(self, execution_id: str) -> bool: ...
        # 仅更新 DB，Worker 检测后中断
```

### 5.2 sse_bus_pg.py - 基于 DB 的 SSE 事件总线

**职责**：事件发布、订阅（兼容原接口）

```python
# 核心接口（与原 sse_bus.py 接口一致）
async def publish(execution_id: str, event: str, data: dict) -> None: ...
    # INSERT INTO execution_events

async def subscribe(execution_id: str) -> AsyncGenerator[str, None]: ...
    # 1. SELECT 历史事件 ORDER BY seq
    # 2. 轮询 SELECT 新事件 WHERE seq > :last
    # 3. yield SSE 格式字符串
```

### 5.3 pg_worker.py - PostgreSQL Worker

**职责**：轮询队列、执行任务、自适应频率

```python
class PGWorker:
    def __init__(self, poll_interval_fast: float = 0.1, poll_interval_slow: float = 5.0):
        self.fast = poll_interval_fast    # 100ms
        self.slow = poll_interval_slow    # 5000ms
        self.current_interval = self.slow

    async def run(self):
        while True:
            job = await self.queue.dequeue(worker_id=self.worker_id)
            if job:
                self.current_interval = self.fast  # 有任务，快速轮询
                await self._execute_job(job)
            else:
                self.current_interval = self.slow   # 无任务，节能模式
                await asyncio.sleep(self.slow)

    async def _execute_job(self, job: dict):
        # 1. 加载 execution + workflow definition
        # 2. 构建 LangGraph
        # 3. astream 循环（与 ARQ 版本相同逻辑）
        # 4. 每节点 publish 事件
        # 5. 完成/失败 → complete()
```

### 5.4 与原接口对比

| 模块 | 原文件 | 新文件 | 接口变化 |
|------|--------|--------|----------|
| 队列客户端 | `arq_client.py` | `pg_queue.py` | `enqueue` 签名不变 |
| 事件总线 | `sse_bus.py` | `sse_bus_pg.py` | `publish`/`subscribe` 签名不变 |
| Worker | `worker/app.py` | `worker/pg_worker.py` | 独立进程入口 |

---

## 六、API 端点改造

### 6.1 POST /workflows/{id}/execute

```python
@router.post("/{wid}/execute")
async def execute(wid: str, body: ExecuteRequest, me=Depends(get_current_user)):
    # 改造：改用 pg_queue.enqueue
    from app.core.engine.pg_queue import PGJobQueue
    queue = PGJobQueue()
    exec_id = await queue.enqueue(
        workflow_id=wid,
        inputs=body.inputs or {},
        trigger="manual",
        user_id=str(me.id)
    )
    # 无需等待，立即返回
    return ok({"executionId": exec_id, "status": "running"})
```

### 6.2 GET /executions/{id}/stream

```python
@router.get("/{eid}/stream")
async def stream(eid: str, me=Depends(get_current_user)):
    from app.core.engine.sse_bus_pg import subscribe
    
    async def event_gen():
        async for event in subscribe(eid, poll_interval=0.5):  # 500ms 轮询
            yield event
    
    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"}
    )
```

### 6.3 POST /executions/{id}/resume

```python
@router.post("/{eid}/resume")
async def resume(eid: str, me=Depends(get_current_user)):
    from app.core.engine.pg_queue import PGJobQueue
    queue = PGJobQueue()
    # 重新入队，Worker 检测 checkpoint 后断点恢复
    await queue.requeue(eid)
    return ok({"success": True})
```

---

## 七、Agent 工具改造

### 7.1 _workflow_tool

```python
def _workflow_tool(wf: Workflow):
    async def _run(**kwargs) -> str:
        from app.core.engine.pg_queue import PGJobQueue
        queue = PGJobQueue()
        exec_id = await queue.enqueue(
            str(wf.id), kwargs, trigger="agent", user_id=None
        )
        # 轮询 DB 查询状态（与改造前相同逻辑）
        for _ in range(WORKFLOW_TIMEOUT_SECONDS):
            row = await _get_execution(exec_id)
            if row and row.status in ("completed", "failed", "cancelled"):
                if row.outputs:
                    return json.dumps(row.outputs, ensure_ascii=False)
                return f"工作流{row.status}"
            await asyncio.sleep(1)
        return "工作流执行超时"

    return StructuredTool.from_function(...)
```

---

## 八、错误处理与恢复

### 8.1 Worker 崩溃恢复

| 场景 | 检测 | 恢复 |
|------|------|------|
| Worker 进程崩溃 | job_queue.status='running' 超时 | 定时任务重置为 'pending'，retry_count++ |
| Worker 重启 | 新 Worker 启动 | 轮询继续，checkpoint 恢复执行 |
| PostgreSQL 重启 | 连接断开异常 | 连接池自动重连，Worker 继续轮询 |

### 8.2 重复执行防护

```python
# dequeue 使用 SKIP LOCKED 保证原子性
async def dequeue(self, worker_id: str) -> dict | None:
    async with async_session() as s:
        async with s.begin():
            result = await s.execute(
                text("""
                    SELECT execution_id, inputs
                    FROM job_queue
                    WHERE status = 'pending'
                    ORDER BY priority DESC, created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                """)
            )
            job = result.fetchone()
            if job:
                await s.execute(
                    text("""
                        UPDATE job_queue
                        SET status = 'running',
                            worker_id = :wid,
                            started_at = NOW()
                        WHERE execution_id = :eid
                    """),
                    {"eid": job.execution_id, "wid": worker_id}
                )
            await s.commit()
            return job
```

### 8.3 超时处理

```python
# 定时任务（每 5 分钟）
async def timeout_stuck_jobs():
    """将运行中超时的任务标记为失败"""
    await s.execute(
        text("""
            UPDATE job_queue
            SET status = 'failed',
                error_msg = 'Worker timeout',
                completed_at = NOW()
            WHERE status = 'running'
              AND started_at < NOW() - INTERVAL '10 minutes'
        """)
    )
```

---

## 九、性能考量

### 9.1 轮询频率

| 场景 | 频率 | 说明 |
|------|------|------|
| 有任务时 | 100ms | 快速处理积压 |
| 无任务时 | 5000ms | 降低 DB 负载 |
| SSE 轮询 | 500ms | 平衡实时性与 DB 压力 |

### 9.2 数据库索引

- `job_queue`: `(status, priority DESC, created_at ASC)` - 出队查询
- `execution_events`: `(execution_id, seq)` - 事件查询

### 9.3 连接池

- Worker: 5-10 连接（主要消耗）
- API: 5 连接（轮询 SSE）

### 9.4 预估负载

| 指标 | 预估 |
|------|------|
| 并发执行 | 10-50（受 LangGraph 限制） |
| DB QPS | 100-500（含轮询） |
| 事件存储 | 1KB/事件，自动清理 |

---

## 十、文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `core/engine/pg_queue.py` | 新增 | PostgreSQL 队列客户端 |
| `core/engine/sse_bus_pg.py` | 新增 | 基于 DB 的 SSE 事件总线 |
| `worker/pg_worker.py` | 新增 | PostgreSQL Worker（独立进程） |
| `worker/pg_worker_main.py` | 新增 | Worker 启动入口 |
| `core/engine/arq_client.py` | 修改 | 内部改用 pg_queue（保持兼容） |
| `core/engine/sse_bus.py` | 保留 | 可选保留，或标记 deprecated |
| `api/v2/workflows.py` | 修改 | execute 端点改用 pg_queue |
| `api/v2/executions.py` | 修改 | stream/resume/cancel 改造 |
| `core/agent/tool_registry.py` | 修改 | 改用 pg_queue |
| `api/v2/health.py` | 修改 | 添加 Worker 健康检查端点 |
| `scripts/init_pg_queue.sql` | 新增 | 数据库初始化脚本 |
| `tests/test_pg_queue.py` | 新增 | 队列单元测试 |
| `tests/test_pg_worker.py` | 新增 | Worker 单元测试 |
| `tests/test_sse_bus_pg.py` | 新增 | SSE 事件流测试 |

---

## 十一、部署与运维

### 11.1 数据库迁移

```bash
# 执行 SQL 初始化
psql -d easyrag -f scripts/init_pg_queue.sql
```

### 11.2 Worker 启动

```bash
# 开发
python -m app.worker.pg_worker_main

# 生产（多 Worker）
python -m app.worker.pg_worker_main --worker-id=worker-1 &
python -m app.worker.pg_worker_main --worker-id=worker-2 &
python -m app.worker.pg_worker_main --worker-id=worker-3 &
```

### 11.3 监控

| 指标 | 查询 |
|------|------|
| 待处理任务数 | `SELECT COUNT(*) FROM job_queue WHERE status='pending'` |
| 运行中任务数 | `SELECT COUNT(*) FROM job_queue WHERE status='running'` |
| Worker 健康 | `SELECT worker_id, COUNT(*) FROM job_queue WHERE status='running' GROUP BY worker_id` |

---

## 十二、回滚策略

如需回滚到 Redis 方案：
1. 停止 PostgreSQL Worker
2. 恢复 `arq_client.py` 和 `sse_bus.py` 的引用
3. 启动 ARQ Worker
4. 待处理任务需手动处理（导出 job_queue 到 Redis）

---

## 十三、约束

- **前端契约不变** — `/workflows/:id/execute` 仍返回 `{executionId, status}`，`/executions/:id/stream` 仍返回 SSE
- **SSE 事件名不变** — `execution_start` / `node_start` / `node_complete` / `execution_complete` / `execution_paused` / `error` / `execution_cancelled`
- **Agent 工具接口不变** — `_workflow_tool` 仍返回结构化结果
- **Checkpoint 兼容** — PostgresSaver 配置保持不变
- **技术栈** — PostgreSQL 14+（`SKIP LOCKED` 支持）

---

## 十四、测试策略

| 测试类型 | 覆盖点 |
|----------|--------|
| 单元测试 | `pg_queue.enqueue/dequeue/complete` 原子性 |
| 单元测试 | `sse_bus_pg.publish/subscribe` 事件顺序 |
| 集成测试 | Worker 轮询 → 执行 → 完成 全流程 |
| 并发测试 | 多 Worker 并发 dequeue（无重复执行） |
| 故障测试 | Worker 崩溃 → 任务重试 → 断点恢复 |
| 性能测试 | 100 并发执行，轮询频率影响 |

---

## 文档版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| V1.0 | 2026-08-31 | PostgreSQL 持久化工作流队列设计方案 |

---

*— 文档结束 —*
