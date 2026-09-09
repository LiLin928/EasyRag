# Celery + Redis Streams 集成指南

## 已创建文件清单

### 核心配置
| 文件 | 说明 |
|------|------|
| `app/core/celery_app.py` | Celery 应用配置（队列路由、重试等） |
| `app/core/redis_streams.py` | Redis Streams 事件总线封装 |

### 任务模块
| 文件 | 说明 |
|------|------|
| `app/worker/tasks/__init__.py` | 任务模块导出 |
| `app/worker/tasks/parse_tasks.py` | 文档解析任务（含进度推送） |
| `app/worker/tasks/workflow_tasks.py` | 工作流执行任务 |
| `app/worker/tasks/agent_tasks.py` | Agent 对话任务 |

### SSE 端点
| 文件 | 说明 |
|------|------|
| `app/api/v2/sse_streams.py` | 基于 Streams 的 SSE 端点 |

### 服务层示例
| 文件 | 说明 |
|------|------|
| `app/services/document_service_v2.py` | 文档服务 V2（Celery 版） |

### 启动脚本
| 文件 | 说明 |
|------|------|
| `celery_worker_main.py` | Celery Worker 启动入口 |

---

## 环境准备

### 1. 安装依赖

```bash
pip install celery redis

# 或使用 uv
uv add celery redis
```

### 2. 启动 Redis

```bash
# Docker
docker run -d -p 6379:6379 --name easyrag-redis redis:7-alpine

# 或使用本地 Redis
redis-server
```

### 3. 配置环境变量

```bash
# .env
REDIS_URL=redis://localhost:6379
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

---

## 启动命令

### 启动 Celery Worker

```bash
# 启动所有队列
python celery_worker_main.py

# 启动指定队列
python celery_worker_main.py -Q parse -c 4
python celery_worker_main.py -Q workflow,agent -c 8

# 调试模式
python celery_worker_main.py -l debug
```

### 启动 FastAPI

```bash
uvicorn app.main:app --reload
```

---

## 队列说明

| 队列 | 用途 | 并发建议 |
|------|------|---------|
| `default` | 默认任务 | 4 |
| `parse` | 文档解析 | 根据存储 I/O 调整 |
| `workflow` | 工作流执行 | 8-16 |
| `agent` | Agent 对话 | 4-8 |

---

## API 使用示例

### 1. 上传文档并解析

```python
# 服务层调用
from app.services.document_service_v2 import DocumentServiceV2

result = await DocumentServiceV2.upload_document(
    session=session,
    kb_id=1,
    filename="example.pdf",
    file_key="1/123/example.pdf",
    file_size=1024000,
    user_id=1,
)

# 返回
# {
#   "doc_id": 123,
#   "task_id": "abc-123",
#   "status": "enqueued"
# }
```

### 2. 订阅解析进度（SSE）

```javascript
// 前端
import { fetchEventSource } from "@microsoft/fetch-event-source";

await fetchEventSource(`/api/v2/sse/parse-tasks/${docId}/stream`, {
  onmessage(msg) {
    const data = JSON.parse(msg.data);
    console.log(data.event, data.data.pct);
  }
});
```

### 3. 提交工作流任务

```python
from app.core.celery_app import celery_app

task = celery_app.send_task(
    "execute_workflow",
    args=[execution_id, definition, debug],
    queue="workflow"
)
```

---

## 迁移指南

### 从 V1 (PG Queue) 迁移到 V2 (Celery)

#### 任务提交

```python
# V1 (旧)
from app.core.engine.pg_queue import PGJobQueue

await PGJobQueue.enqueue_task(
    "parse_document",
    {"doc_id": doc_id}
)

# V2 (新)
from app.core.celery_app import celery_app

task = celery_app.send_task(
    "parse_document",
    args=[doc_id, file_key, kb_id],
    queue="parse"
)
```

#### 事件发布

```python
# V1 (旧)
from app.core.engine.sse_bus_pg import publish

await publish(execution_id, "node_complete", data)

# V2 (新)
from app.core.redis_streams import publish_event

await publish_event(
    f"workflow:{execution_id}",
    "node_completed",
    data
)
```

---

## 监控

### Flower (Celery 监控)

```bash
pip install flower

# 启动
celery -A app.core.celery_app flower --port=5555

# 访问 http://localhost:5555
```

### Redis CLI

```bash
# 查看 Stream 长度
XLEN parse:123
XLEN workflow:456

# 查看消费者组
XINFO GROUPS parse:123

# 查看 Stream 信息
XINFO STREAM workflow:456
```

---

## 常见问题

### Q: Worker 启动失败？
A: 检查 Redis 连接：`redis-cli ping`

### Q: 任务没有执行？
A: 检查队列名称是否匹配，Worker 是否监听正确队列

### Q: SSE 没有推送？
A: 检查 Stream Key 是否正确，Consumer Group 是否存在

### Q: 内存占用过高？
A: 检查 Stream 的 `maxlen` 设置，适当减小保留数量

---

## 后续优化

- [ ] 添加 Celery Beat 定时任务
- [ ] 配置任务优先级
- [ ] 实现死信队列
- [ ] 添加分布式锁
- [ ] 集成 Langfuse 追踪
