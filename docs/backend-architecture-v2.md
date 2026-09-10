# EasyRAG 后端架构文档

> 更新日期: 2026-09-10
> 版本: v2.0 (Celery-only)

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

| 队列名 | 用途 | Worker 文件 | 主要任务 |
|--------|------|-------------|----------|
| `parse` | 文档解析 | `parse_tasks.py` | `parse_document` |
| `workflow` | 工作流执行 | `workflow_tasks.py` | `execute_workflow` |
| `agent` | Agent 对话 | `agent_tasks.py` | `execute_agent_chat` |
| `default` | 其他任务 | `parse_tasks.py` | `execute_retrieval_test` |

### 任务配置

```python
# app/core/celery_app.py
task_routes = {
    "parse.*": {"queue": "parse"},
    "workflow.*": {"queue": "workflow"},
    "agent.*": {"queue": "agent"},
}
```

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

## 参考文档

- Celery 文档: https://docs.celeryq.dev/
- LangGraph 文档: https://langchain-ai.github.io/langgraph/
- FastAPI 文档: https://fastapi.tiangolo.com/
- 项目设计文档: `docs/backend-plans/`