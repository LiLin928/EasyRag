# EasyRAG 后端架构文档

> 更新日期: 2026-09-10
> 版本: v2.1 (Celery + Enhanced Infrastructure)

---

## 架构概览

EasyRAG 后端采用 **Celery + Redis + PostgreSQL** 的异步任务处理架构。

### 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI App                          │
│                      (API Layer)                            │
└──────────────┬──────────────────────────────────────────────┘
               │
               ├──► API Routes (app/api/v2/)
               │    ├── Documents & Assets
               │    ├── Agents
               │    ├── Workflows
               │    ├── Webhooks
               │    └── Retrieval Tests
               │
               ├──► Services (app/services/)
               │    ├── AgentService
               │    ├── RetrievalTestService
               │    └── DocumentService
               │
               └──► Celery Client (app/core/engine/celery_client.py)
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                     Redis (Broker)                          │
│              celery_app.send_task()                         │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│                   Celery Workers                            │
│                  (Task Execution)                           │
├─────────────────────────────────────────────────────────────┤
│  parse queue    │ workflow queue │ agent queue │ default   │
│  (parse_tasks)  │(workflow_tasks)│(agent_tasks)│           │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│                  PostgreSQL (Storage)                       │
│         ├── WorkflowExecutions                             │
│         ├── Documents & Chunks                             │
│         └── Agent Conversations                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 任务队列设计

### 队列分类

| 队列名 | 用途 | Worker 文件 | 主要任务 | 优先级 |
|--------|------|-------------|----------|--------|
| `high` | 高优先级任务 | `workflow_tasks.py` | `workflow.urgent` | 最高 |
| `default` | 常规任务 | `parse_tasks.py` | `execute_retrieval_test` | 中等 |
| `low` | 低优先级任务 | `parse_tasks.py` | `cleanup.*`, `retrieval_test.*` | 低 |
| `parse` | 文档解析 | `parse_tasks.py` | `parse_document` | 业务队列 |
| `workflow` | 工作流执行 | `workflow_tasks.py` | `execute_workflow` | 业务队列 |
| `agent` | Agent 对话 | `agent_tasks.py` | `execute_agent_chat` | 业务队列 |

### 任务配置

```python
# app/core/celery_app.py
task_routes = {
    "parse.*": {"queue": "parse"},
    "workflow.*": {"queue": "workflow"},
    "agent.*": {"queue": "agent"},
    "workflow.urgent": {"queue": "high"},
    "cleanup.*": {"queue": "low"},
    "retrieval_test.*": {"queue": "low"},
}
```

### 优先级队列

Celery 支持 0-9 的优先级范围（9 最高），通过 `priority` 参数指定：

```python
# 提交高优先级任务
execution_id = await enqueue_workflow_task(
    workflow_id=str(workflow_id),
    inputs={"param": "value"},
    trigger="manual",
    user_id=str(user_id),
    priority=9  # 高优先级（>= 7 使用 high 队列）
)

# 提交低优先级任务
execution_id = await enqueue_workflow_task(
    workflow_id=str(workflow_id),
    inputs={},
    trigger="manual",
    user_id=None,
    priority=1  # 低优先级（< 3 使用 low 队列）
)
```

**优先级映射规则：**
- `priority >= 7` → `high` 队列（紧急任务）
- `priority >= 3` → 业务队列（`workflow`/`parse`/`agent`）
- `priority < 3` → `low` 队列（后台清理等）

**验证与错误处理：**
- 优先级参数自动验证（必须在 0-9 范围内）
- 数据库事务与任务提交原子性保证
- 任务提交失败时自动回滚

---

## 核心功能调用方式

### 1. 文档解析

#### API 入口
```python
# app/api/v2/assets.py
@router.post("/documents/upload")
async def upload(file: UploadFile, kbId: str, me=Depends(get_current_user)):
    # 保存文件到存储
    storage = get_storage()
    await storage.put(key, data)
    
    # 提交 Celery 任务
    celery_app.send_task(
        "parse_document",  # 任务名称
        args=[doc_id, key, kbId],
        queue="parse",
        task_id=task_id,
    )
```

#### Worker 处理
```python
# app/worker/tasks/parse_tasks.py
@celery_app.task(bind=True, max_retries=3)
def parse_document(self, doc_id: str, file_key: str, kb_id: str) -> dict:
    # 1. 下载文件
    storage = get_storage()
    file_data = await storage.get(file_key)
    
    # 2. 解析文档
    dispatcher = DocumentDispatcher()
    parsed_doc = await dispatcher._dispatch_from_data(file_data, file_key, doc_id)
    
    # 3. 构建文档树
    tree_builder = TreeBuilder()
    tree = await tree_builder.build(parsed_doc.elements, doc_id)
    
    # 4. 分块
    chunker = Chunker()
    chunks = await chunker.chunk(parsed_doc.elements, doc_id, kb_id)
    
    # 5. 向量化
    embedder = Embedder()
    await embedder.embed(chunks, kb_id)
    
    # 6. 发布进度到 Redis Streams
    publish_event(stream_key, "task_completed", result)
```

#### SSE 订阅
```python
# 前端订阅进度
GET /api/v2/sse/parse-tasks/{doc_id}/stream
```

---

### 2. Agent 对话

#### 方式一：API 直连（推荐）

适用于需要 SSE 实时流式输出的场景。

```python
# app/api/v2/agents.py
@router.post("/{agent_id}/chat")
async def chat(agent_id: str, body: ChatRequest, me=Depends(get_current_user)):
    svc = AgentService()
    
    async def event_generator():
        async for event in svc.chat(agent_id, body.question, me.id):
            yield event  # SSE 事件
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

#### 方式二：Celery 任务

适用于后台执行，通过 Redis Streams 订阅结果。

```python
# 提交任务
celery_app.send_task(
    "execute_agent_chat",
    args=[agent_id, chat_id, question],
    queue="agent",
)

# Worker 执行
# app/worker/tasks/agent_tasks.py
@celery_app.task(bind=True)
def execute_agent_chat(self, agent_id, chat_id, question):
    svc = AgentService()
    async for event in svc.chat(agent_id, question, user_id):
        # 转发到 Redis Streams
        _publish_sync(f"agent:{chat_id}", event_type, data)
```

#### AgentService 内部实现

```python
# app/services/agent_service.py
class AgentService:
    async def chat(self, agent_id: str, question: str, user_id) -> AsyncIterator[str]:
        # 1. 构建 LangGraph React Agent
        from langgraph.prebuilt import create_react_agent
        
        llm = await build_chat_model_by_name(agent.model)
        tools = await build_tools(agent)
        
        react = create_react_agent(
            model=llm,
            tools=tools,
            prompt=SystemMessage(content=agent.prompt),
            checkpointer=await get_checkpointer(),
        )
        
        # 2. 流式执行
        async for ev in react.astream_events({"messages": [{"role": "user", "content": question}]}, config=config):
            if ev["event"] == "on_chat_model_stream":
                yield sse_event("token", {"token": ev["data"]["chunk"].content})
            elif ev["event"] == "on_tool_start":
                yield sse_event("tool_start", {"tool": ev["name"]})
            # ...
```

---

### 3. 工作流执行

#### API 入口

```python
# app/api/v2/workflows.py 或 webhooks.py
from app.core.engine.celery_client import enqueue_workflow_task

execution_id = await enqueue_workflow_task(
    workflow_id=str(workflow_id),
    inputs={"param": "value"},
    trigger="manual",  # manual/api/webhook/agent
    user_id=str(user_id)
)
```

#### enqueue_workflow_task 实现

```python
# app/core/engine/celery_client.py
async def enqueue_workflow_task(
    workflow_id: str,
    inputs: dict | None,
    trigger: str,
    user_id: str | None,
) -> str:
    async with async_session() as s:
        # 1. 加载 workflow 定义
        wf = await s.get(Workflow, workflow_id)
        definition = wf.definition or {}
        
        # 2. 创建 WorkflowExecution 记录
        execution = WorkflowExecution(
            workflow_id=wf.id,
            inputs=inputs or {},
            trigger_type=trigger,
            status="pending",
        )
        s.add(execution)
        await s.commit()
        
        # 3. 提交 Celery 任务
        celery_app.send_task(
            "execute_workflow",
            args=[str(execution.id), definition, inputs or {}],
            queue="workflow",
            task_id=str(execution.id),
        )
        
        return str(execution.id)
```

#### Worker 执行

```python
# app/worker/tasks/workflow_tasks.py
@celery_app.task(bind=True, max_retries=3)
def execute_workflow(self, execution_id: str, definition: dict, inputs: dict):
    # 1. 构建 LangGraph
    from app.core.engine.graph_builder import GraphBuilder
    
    builder = GraphBuilder()
    graph = await builder.build(definition, execution_id, debug=False)
    
    # 2. 准备初始状态
    initial_state = {
        "execution_id": execution_id,
        "inputs": inputs,
        "node_outputs": {},
    }
    
    # 3. 执行工作流
    async for event in graph.astream_events(initial_state, config=config):
        # 发布节点事件
        _publish_sync(f"workflow:{execution_id}", "node_completed", event)
    
    # 4. 获取最终状态
    final_state = await graph.aget_state(config)
    return {"status": "completed", "outputs": final_state.values}
```

---

### 4. 检索测试

#### API 入口

```python
# app/api/v2/retrieval_testing.py
@router.post("/retrieval-test-sets/{set_id}/runs")
async def start_run(set_id: str, body: RetrievalRunCreate):
    # 创建测试运行记录
    run = await service.start_run(test_set_id=set_id, ...)
    
    if run._newly_created:
        # 提交 Celery 任务
        from app.worker.tasks.parse_tasks import execute_retrieval_test
        execute_retrieval_test.delay(str(run.id))
    
    return ok(service.test_run_output(run))
```

#### Worker 执行

```python
# app/worker/tasks/parse_tasks.py
@celery_app.task(bind=True, max_retries=2)
def execute_retrieval_test(self, config_id: int):
    from app.services.retrieval_test_service import execute_run
    await execute_run(run_id)
```

---

## Worker 启动方式

### 单个 Worker

```bash
# Parse worker
celery -A app.core.celery_app worker -Q parse -l info -c 4

# Workflow worker
celery -A app.core.celery_app worker -Q workflow -l info -c 2

# Agent worker
celery -A app.core.celery_app worker -Q agent -l info -c 2

# Default worker
celery -A app.core.celery_app worker -Q default -l info -c 2
```

### 多队列 Worker

```bash
# 处理所有队列
celery -A app.core.celery_app worker \
  -Q default,parse,workflow,agent \
  -l info \
  -c 8
```

### 生产环境启动

```bash
# 使用 supervisord 或 systemd 管理
# 示例 supervisord.conf
[program:easyrag_worker]
command=celery -A app.core.celery_app worker -Q default,parse,workflow,agent -l info
directory=/app/backend
user=easyrag
autostart=true
autorestart=true
```

---

## 事件推送（Redis Streams）

### 发布事件

```python
# app/core/redis_streams.py
async def publish_event(stream: str, event_type: str, payload: dict):
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    r = redis.from_url(redis_url)
    
    data = {
        "type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "payload": json.dumps(payload),
    }
    
    r.xadd(stream, data, maxlen=10000)
```

### SSE 订阅

```python
# app/api/v2/sse_streams.py
@router.get("/executions/{execution_id}/stream")
async def stream_execution_events(execution_id: str):
    stream_key = f"workflow:{execution_id}"
    
    async def event_generator():
        async for stream, event in subscribe_events([stream_key]):
            yield sse_event(event.event_type, event.payload)
            
            if event.event_type in ["execution_completed", "execution_failed"]:
                break
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## 监控与健康检查

### 健康检查端点

```python
# app/api/v2/health.py
@router.get("/workers")
async def worker_health():
    inspect = celery_app.control.inspect()
    
    return {
        "queue": {
            "pending": sum(len(tasks) for tasks in inspect.reserved().values()),
            "running": sum(len(tasks) for tasks in inspect.active().values()),
        },
        "workers": list(inspect.stats().keys()),
    }
```

### Celery Flower 监控

```bash
# 启动 Flower UI
celery -A app.core.celery_app flower --port=5555

# 访问 http://localhost:5555
```

---

## 错误处理与重试

### 任务重试配置

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    time_limit=3600,  # 1小时超时
)
def execute_workflow(self, execution_id: str, ...):
    try:
        # 执行任务
        ...
    except Exception as exc:
        # 发布失败事件
        _publish_sync(f"workflow:{execution_id}", "execution_failed", {"error": str(exc)})

        # 重试
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60)
        raise
```

---

## 死信队列管理

当任务达到最大重试次数后，会被添加到死信队列（Dead Letter Queue），便于人工介入处理。

### 数据库表

```sql
CREATE TABLE dead_letter_tasks (
    id UUID PRIMARY KEY,
    task_id VARCHAR(100) UNIQUE NOT NULL,
    task_name VARCHAR(255) NOT NULL,
    args JSONB,                    -- 任务位置参数
    kwargs JSONB,                  -- 任务关键字参数
    exception TEXT NOT NULL,       -- 异常信息
    traceback TEXT,                -- 堆栈跟踪
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    retried_at TIMESTAMPTZ,        -- 重试时间
    retried_by UUID REFERENCES users(id)  -- 重试操作用户
);

CREATE INDEX idx_dlq_task_id ON dead_letter_tasks(task_id);
CREATE INDEX idx_dlq_status ON dead_letter_tasks(status);
CREATE INDEX idx_dlq_created_at ON dead_letter_tasks(created_at);
```

### API 接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v2/dead-letter/tasks` | GET | 列出死信任务（支持状态过滤和分页） |
| `/api/v2/dead-letter/tasks/{task_id}/retry` | POST | 重试指定任务 |
| `/api/v2/dead-letter/tasks/{task_id}/ignore` | POST | 忽略指定任务（标记为已处理） |
| `/api/v2/dead-letter/stats` | GET | 获取统计信息（总数、按状态/类型统计、最近24小时） |

#### 示例请求

```bash
# 列出待处理的死信任务
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v2/dead-letter/tasks?status=pending&limit=50"

# 重试任务
curl -X POST \
  -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v2/dead-letter/tasks/{task_id}/retry"

# 获取统计信息
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v2/dead-letter/stats"
```

### 告警机制

支持多种告警渠道，通过环境变量配置：

```bash
# 邮件告警
ALERT_EMAIL=admin@example.com

# Slack Webhook
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx

# 钉钉 Webhook
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxx
```

### 定时任务

| 任务名称 | 执行频率 | 说明 |
|---------|---------|------|
| `dlq.monitor` | 每小时 | 检查死信队列并发送告警 |
| `dlq.cleanup` | 每天 02:00 | 清理过期任务（默认保留30天） |
| `dlq.add_to_dlq` | 按需 | 异步添加失败任务到死信队列 |

### 工作流程

```
任务失败
  ↓
达到最大重试次数？
  ├─ 否 → 自动重试
  └─ 是 → 添加到死信队列
           ↓
       持久化到数据库
           ↓
       发布到 Redis Streams
           ↓
       定时告警通知
           ↓
       人工介入处理
           ├─ 重试 → 重新提交到队列
           └─ 忽略 → 标记为已处理
```

### 监控指标

建议监控以下指标：

- 死信任务总数（`total_failed`）
- 最近24小时新增数（`last_24h`）
- 按任务类型分布（`by_task_type`）
- 按状态分布（`by_status`）

---

## 数据库连接管理

### Async Session

```python
# app/db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)
```

### 使用方式

```python
async with async_session() as session:
    # 数据库操作
    result = await session.execute(select(Document))
    docs = result.scalars().all()
    await session.commit()
```

---

## 迁移指南

### 从 PGWorker 迁移到 Celery

| 旧方式 (PGWorker) | 新方式 (Celery) |
|-------------------|-----------------|
| `PGJobQueue.enqueue()` | `celery_app.send_task()` |
| `PGJobQueue.enqueue_task()` | `task.delay()` |
| `PGWorker._execute_workflow()` | `execute_workflow` 任务 |
| `PGWorker._execute_retrieval_test()` | `execute_retrieval_test` 任务 |

---

## 性能优化

### 并发配置

```python
# pyproject.toml 或环境变量
WORKER_CONCURRENCY=8
WORKER_PREFETCH_MULTIPLIER=1
```

### 队列优先级

```python
# 高优先级任务
celery_app.send_task("urgent_task", args=[...], priority=10)

# 低优先级任务
celery_app.send_task("batch_task", args=[...], priority=1)
```

---

## 故障排查

### 查看任务状态

```bash
# 查看活跃任务
celery -A app.core.celery_app inspect active

# 查看保留任务
celery -A app.core.celery_app inspect reserved

# 查看 worker 统计
celery -A app.core.celery_app inspect stats
```

### 日志查看

```bash
# Worker 日志
tail -f /var/log/celery/worker.log

# 或直接查看控制台输出
celery -A app.core.celery_app worker -l debug
```

---

## Tracing 系统

### 嵌套 Span 支持

EasyRAG 支持嵌套的 span 追踪，自动管理父子关系，适用于复杂的调用链追踪。

#### 基本用法

```python
from app.providers.trace.span_manager import traced_span

async def chat(self, agent_id: str, question: str, user_id: str):
    """Agent 对话。"""
    with traced_span("agent.chat", attributes={"agent_id": agent_id, "user_id": user_id}):
        # 加载 Agent 配置
        with traced_span("agent.load_config"):
            agent = await self._load_agent(agent_id)

        # 构建 React Agent
        with traced_span("agent.build_react"):
            react = await self._build_react_agent(agent)

        # 执行对话
        with traced_span("agent.execute"):
            async for event in react.astream_events(...):
                yield event
```

#### 特性

- **自动管理父子关系**：嵌套的 span 自动建立父子关系
- **协程安全**：使用 `contextvars` 保证异步环境下的正确性
- **多后端支持**：支持 Langfuse 和 LangSmith
- **性能追踪**：自动记录 span 持续时间
- **多层嵌套**：支持任意深度的 span 嵌套

#### Span 上下文

```python
@dataclass
class SpanContext:
    """Span 上下文。"""
    trace_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    current_span_id: Optional[str] = None
    depth: int = 0
    spans: list = field(default_factory=list)
```

---

## SSE 连接管理

### 连接追踪与清理

SSE（Server-Sent Events）连接管理器自动追踪活跃连接并清理过期连接。

#### 连接生命周期

```
客户端建立 SSE 连接
  ↓
注册连接（connection_id + stream_key）
  ↓
更新活动时间（每次事件）
  ↓
连接关闭或超时
  ↓
注销连接
```

#### 配置

```python
# 默认超时时间：5 分钟无活动
SSEConnectionManager(timeout_seconds=300)
```

#### 使用示例

```python
from app.sse.manager import get_sse_manager

manager = get_sse_manager()

# 注册连接
await manager.register(
    connection_id=str(uuid.uuid4()),
    stream_key=f"workflow:{execution_id}",
    client_ip=request.client.host
)

# 更新活动时间
await manager.update_activity(connection_id)

# 注销连接
await manager.unregister(connection_id)
```

#### 定时清理

Celery Beat 每 5 分钟自动清理过期连接：

```python
# Celery 配置
celery_app.conf.beat_schedule = {
    "cleanup-sse": {
        "task": "sse.cleanup_expired",
        "schedule": crontab(minute="*/5"),
    },
}
```

#### 统计信息

```python
stats = await manager.get_stats()
# 返回：
{
    "total_connections": 10,
    "by_stream": {
        "workflow:xxx": 5,
        "agent:yyy": 3,
        "parse:zzz": 2
    },
    "oldest_connection": 1634567890.123
}
```

---

## 工具执行器

### 结构化返回结果

工具执行器返回结构化的执行结果，包含详细的错误信息和统计。

#### ToolExecutionResult

```python
@dataclass
class ToolExecutionResult:
    """工具执行结果。"""
    success: bool                    # 是否成功
    data: Optional[dict]            # 返回数据
    error: Optional[str]            # 错误信息
    duration_ms: float              # 执行时长（毫秒）
    status_code: Optional[int]      # HTTP 状态码
    cached: bool                    # 是否来自缓存
```

#### 执行示例

```python
from app.core.tools.executor import execute

result = await execute(
    tool=http_tool,
    args={"url": "https://api.example.com/data"},
    timeout=30,  # 超时时间（秒）
    cache_key="tool:123"  # 可选，启用缓存
)

if result.success:
    print(f"执行成功，耗时 {result.duration_ms}ms")
    print(f"返回数据：{result.data}")
else:
    print(f"执行失败：{result.error}")
```

#### 支持的工具类型

| 类型 | 说明 | 特性 |
|------|------|------|
| HTTP | HTTP 请求工具 | 超时控制、认证处理、错误分类 |
| Python | Python 代码工具 | 沙箱执行、降级执行 |
| 内置 | 内置工具 | 直接调用、类型安全 |

#### 错误处理

- **HTTP 工具**：区分成功、超时、请求错误、认证失败
- **Python 工具**：区分无代码配置、执行错误、沙箱不可用
- **内置工具**：区分工具不存在、执行错误

---

## 沙箱客户端

### 自动重试机制

OpenSandbox 客户端支持自动重试和指数退避，提高容错能力。

#### 配置

```python
client = OpenSandboxClient(
    base_url="http://192.168.137.13:8090",
    timeout=30,
    max_retries=3  # 最大重试次数
)
```

#### 重试装饰器

```python
@with_retry(max_retries=3, backoff_factor=2.0)
async def create_sandbox(self, image: str, command: list[str]) -> SandboxInfo:
    # 创建沙箱
    ...
```

#### 指数退避

重试间隔按指数增长：`wait_time = backoff_factor ** attempt`

- 第 1 次重试：等待 2 秒
- 第 2 次重试：等待 4 秒
- 第 3 次重试：等待 8 秒

#### 可重试的错误

- `httpx.RequestError` - 连接错误
- `httpx.HTTPStatusError` - HTTP 错误（仅 5xx）

**注意**：4xx 错误不会重试，直接抛出异常。

---

## MinIO 存储

### 错误分类

MinIO 存储提供详细的错误分类，便于错误处理和日志分析。

#### 错误类型

```python
class MinioStorageError(Exception):
    """MinIO 存储错误基类。"""
    
class MinioConnectionError(MinioStorageError):
    """MinIO 连接错误。"""
    
class MinioNotFoundError(MinioStorageError):
    """MinIO 对象不存在错误。"""
    
class MinioPermissionError(MinioStorageError):
    """MinIO 权限错误。"""
```

#### 错误信息

每个错误都包含：
- 错误消息
- 操作类型（`upload`/`download`/`delete` 等）
- 对象键（可选）

```python
try:
    await storage.upload("test.txt", b"content")
except MinioPermissionError as e:
    print(f"权限错误 [{e.operation}]: {e.message}")
    print(f"对象键: {e.key}")
```

### 存储接口

完整的存储接口定义，支持本地文件系统和 MinIO 对象存储。

#### 接口方法

| 方法 | 说明 | 参数 |
|------|------|------|
| `upload` | 上传文件 | key, content, content_type?, metadata? |
| `download` | 下载文件 | key |
| `delete` | 删除文件 | key |
| `exists` | 检查文件是否存在 | key |
| `get_metadata` | 获取文件元数据 | key |
| `list_objects` | 列出文件 | prefix?, recursive? |
| `copy` | 复制文件 | source_key, dest_key |
| `get_presigned_url` | 获取预签名 URL | key, expires? |
| `get_size` | 获取文件大小 | key |

#### 元数据结构

```python
{
    "size": 1024,                      # 文件大小（字节）
    "content_type": "text/plain",      # 内容类型
    "last_modified": 1634567890.123,   # 最后修改时间
    "etag": "abc123",                  # ETag
    "metadata": {}                     # 自定义元数据
}
```

#### 示例

```python
from app.core.storage import get_storage

storage = get_storage()

# 上传文件
url = await storage.upload(
    key="documents/report.pdf",
    content=file_bytes,
    content_type="application/pdf",
    metadata={"author": "admin"}
)

# 获取元数据
metadata = await storage.get_metadata("documents/report.pdf")
print(f"文件大小: {metadata['size']} 字节")

# 复制文件
new_url = await storage.copy(
    source_key="documents/report.pdf",
    dest_key="backup/report_2026.pdf"
)

# 列出文件
files = await storage.list_objects(prefix="documents/", recursive=True)

# 获取预签名 URL（仅 MinIO）
url = await storage.get_presigned_url("documents/report.pdf", expires=3600)
```

---

## 性能优化建议

### 并发配置

```python
# pyproject.toml 或环境变量
WORKER_CONCURRENCY=8
WORKER_PREFETCH_MULTIPLIER=1

# 软超时和硬超时
task_soft_time_limit=3300,  # 55分钟，提前5分钟警告
task_time_limit=3600,       # 1小时硬超时

# 延迟确认，避免任务丢失
task_acks_late=True
```

### 监控指标

建议监控以下指标：

- **死信队列**：任务总数、最近24小时新增、按类型分布
- **SSE 连接**：活跃连接数、按流分组、最长连接时长
- **工具执行**：成功率、平均执行时间、错误分布
- **MinIO 存储**：上传/下载成功率、错误类型分布

### 性能调优

#### Celery Worker

```bash
# 使用多个 worker 进程
celery -A app.core.celery_app worker \
  -Q default,parse,workflow,agent \
  -l info \
  -c 8 \
  --max-tasks-per-child=100  # 定期重启 worker 进程
```

#### 数据库连接池

```python
# 配置连接池大小
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True
)
```

#### Redis 连接

```python
# 使用连接池
redis_pool = redis.ConnectionPool(
    host='localhost',
    port=6379,
    max_connections=50
)
```

---

## 参考文档

- Celery 文档: https://docs.celeryq.dev/
- LangGraph 文档: https://langchain-ai.github.io/langgraph/
- FastAPI 文档: https://fastapi.tiangolo.com/
- MinIO Python SDK: https://min.io/docs/minio/linux/developers/python/minio-py.html
- 项目设计文档: `docs/backend-plans/`