# Celery Workers 快速参考

> 更新: 2026-09-10

---

## 快速启动

```bash
# 启动所有队列的 worker
celery -A app.core.celery_app worker -Q default,parse,workflow,agent -l info

# 或分别启动
celery -A app.core.celery_app worker -Q parse -l info      # 文档解析
celery -A app.core.celery_app worker -Q workflow -l info   # 工作流
celery -A app.core.celery_app worker -Q agent -l info      # Agent 对话
```

---

## 常用任务

### 文档解析
```python
from app.core.celery_app import celery_app

# 入队任务
celery_app.send_task(
    "parse_document",
    args=[doc_id, file_key, kb_id],
    queue="parse",
    task_id=task_id,
)

# SSE 订阅
GET /api/v2/sse/parse-tasks/{doc_id}/stream
```

### 工作流执行
```python
from app.core.engine.celery_client import enqueue_workflow_task

execution_id = await enqueue_workflow_task(
    workflow_id=str(workflow_id),
    inputs={"param": "value"},
    trigger="manual",  # manual/api/webhook/agent
    user_id=str(user_id)
)

# SSE 订阅
GET /api/v2/sse/executions/{execution_id}/stream
```

### Agent 对话

#### 方式一：API 直连（推荐）
```python
from app.services.agent_service import AgentService

svc = AgentService()
async for event in svc.chat(agent_id, question, user_id):
    yield event  # SSE 流式输出

# API 端点
POST /api/v2/agents/{agent_id}/chat
```

#### 方式二：Celery 后台
```python
from app.worker.tasks.agent_tasks import execute_agent_chat

execute_agent_chat.delay(agent_id, chat_id, question)

# SSE 订阅
GET /api/v2/sse/agents/{chat_id}/stream
```

### 检索测试
```python
from app.worker.tasks.parse_tasks import execute_retrieval_test

execute_retrieval_test.delay(run_id)

# SSE 订阅
GET /api/v2/sse/retrieval-tests/{config_id}/stream
```

---

## 监控

### Flower UI
```bash
celery -A app.core.celery_app flower --port=5555
# 访问 http://localhost:5555
```

### Inspect 命令
```bash
# 查看活跃任务
celery -A app.core.celery_app inspect active

# 查看 worker 状态
celery -A app.core.celery_app inspect stats

# 查看 reserved 任务
celery -A app.core.celery_app inspect reserved
```

### 健康检查
```bash
curl http://localhost:8000/api/v2/health/workers
```

---

## 配置

### 环境变量
```bash
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
REDIS_URL=redis://localhost:6379
```

### 队列路由
```python
# app/core/celery_app.py
task_routes = {
    "parse.*": {"queue": "parse"},
    "workflow.*": {"queue": "workflow"},
    "agent.*": {"queue": "agent"},
}
```

---

## 重试策略

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 60秒后重试
    time_limit=3600,  # 1小时超时
)
def my_task(self, ...):
    try:
        # 执行任务
        ...
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60)
        raise
```

---

## 事件推送

### 发布事件
```python
from app.core.redis_streams import publish_event

await publish_event(
    stream="workflow:execution_id",
    event_type="node_completed",
    payload={"node_id": "node1", "result": "success"}
)
```

### SSE 订阅
```python
from app.core.redis_streams import subscribe_events

async for stream, event in subscribe_events(["workflow:123"]):
    print(event.event_type, event.payload)
    
    if event.event_type in ["execution_completed", "execution_failed"]:
        break
```

---

## 故障排查

### 任务卡住
```bash
# 检查 worker 日志
celery -A app.core.celery_app worker -l debug

# 清空队列
redis-cli FLUSHDB
```

### 内存泄漏
```bash
# 设置任务硬超时
@celery_app.task(time_limit=300)  # 5分钟

# 重启 worker
pkill -f "celery.*worker"
celery -A app.core.celery_app worker ...
```

---

## 完整文档

- 架构文档: `docs/backend-architecture-v2.md`
- 设计文档: `docs/backend-plans/`
- API 文档: http://localhost:8000/docs