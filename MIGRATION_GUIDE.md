# EasyRAG Celery + Redis Streams 迁移指南

## 已创建文件清单

### Phase 1: 基础设施 ✅

| 文件 | 大小 | 说明 |
|------|------|------|
| `backend/app/core/celery_app.py` | 1,791 B | Celery 配置 |
| `backend/app/core/redis_streams.py` | 6,875 B | Streams 封装 |
| `backend/app/worker/tasks/__init__.py` | 343 B | 任务导出 |
| `backend/app/worker/tasks/parse_tasks.py` | 5,674 B | 文档解析任务 |
| `backend/app/worker/tasks/parse_tasks_v2.py` | - | 数据库集成版 |
| `backend/app/worker/tasks/workflow_tasks.py` | 8,008 B | 工作流任务 |
| `backend/app/worker/tasks/agent_tasks.py` | 5,705 B | Agent 任务 |
| `backend/celery_worker_main.py` | 1,959 B | Worker 启动 |
| `backend/app/api/v2/sse_streams.py` | 6,874 B | Streams SSE 端点 |
| `backend/app/services/document_service_v2.py` | - | V2 服务 |
| `backend/app/services/document_service_celery.py` | - | Celery 集成版 |

### Phase 2: Docker 配置 ✅

| 文件 | 说明 |
|------|------|
| `docker-compose.celery.yml` | 完整 Docker Compose 配置 |
| `backend/Dockerfile.celery` | Celery 支持版 Dockerfile |
| `start-celery.ps1` | 本地开发启动脚本 |

---

## 快速启动

### 方式一: Docker Compose (推荐)

```bash
# 1. 启动所有服务
docker-compose -f docker-compose.celery.yml up -d

# 2. 查看服务状态
docker-compose -f docker-compose.celery.yml ps

# 3. 查看日志
docker-compose -f docker-compose.celery.yml logs -f api
docker-compose -f docker-compose.celery.yml logs -f celery-worker-parse

# 4. 访问服务
# API: http://localhost:8000
# Flower: http://localhost:5555

# 5. 停止服务
docker-compose -f docker-compose.celery.yml down
```

### 方式二: PowerShell 脚本 (本地开发)

```powershell
# 1. 启动 Redis
.\start-celery.ps1 redis

# 2. 启动 API (终端 1)
.\start-celery.ps1 api

# 3. 启动 Worker (终端 2)
.\start-celery.ps1 worker

# 4. 启动 Flower (终端 3, 可选)
.\start-celery.ps1 flower
```

### 方式三: 手动启动

```bash
# 1. 启动 Redis
docker run -d -p 6379:6379 redis:7-alpine

# 2. 安装依赖
cd backend
pip install celery redis

# 3. 配置环境变量
export REDIS_URL=redis://localhost:6379
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/1

# 4. 启动 Worker
python celery_worker_main.py -Q default,parse,workflow,agent -c 4

# 5. 启动 API
uvicorn app.main:app --reload
```

---

## API 使用示例

### 上传文档

```python
# 前端调用示例
import requests

files = {"file": open("document.pdf", "rb")}
response = requests.post(
    "http://localhost:8000/api/v2/documents/upload",
    files=files,
    data={"kb_id": "your-kb-id"},
    headers={"Authorization": "Bearer your-token"}
)

result = response.json()
print(result)
# {
#   "code": 0,
#   "data": {
#     "doc_id": "...",
#     "task_id": "...",
#     "status": "pending"
#   }
# }
```

### 订阅 SSE 进度

```javascript
// 前端 JavaScript
import { fetchEventSource } from "@microsoft/fetch-event-source";

const docId = "your-doc-id";

await fetchEventSource(`/api/v2/sse/parse-tasks/${docId}/stream`, {
  onmessage(msg) {
    const data = JSON.parse(msg.data);
    console.log(`Event: ${data.event}, Progress: ${data.data.pct}%`);
    
    if (data.event === "task_completed") {
      console.log("解析完成!", data.data.result);
    }
  },
  onerror(err) {
    console.error("SSE Error:", err);
  }
});
```

---

## 监控与调试

### Flower 监控

访问 http://localhost:5555 查看:
- 任务队列状态
- Worker 状态
- 任务执行历史
- 失败任务重试

### Redis CLI

```bash
# 查看 Stream 长度
docker exec -it easyrag-redis redis-cli XLEN parse:doc-id

# 查看消费者组
docker exec -it easyrag-redis redis-cli XINFO GROUPS parse:doc-id

# 查看 Stream 信息
docker exec -it easyrag-redis redis-cli XINFO STREAM workflow:exec-id

# 查看队列长度
docker exec -it easyrag-redis redis-cli LLEN celery
```

### 日志查看

```bash
# 查看 Worker 日志
docker logs -f easyrag-celery-parse

# 查看 API 日志
docker logs -f easyrag-api
```

---

## 常见问题

### Q1: Worker 启动失败 "Connection refused"

**原因**: Redis 未启动或连接配置错误

**解决**:
```bash
# 检查 Redis
docker ps | grep redis

# 测试连接
docker exec -it easyrag-redis redis-cli ping

# 检查环境变量
echo $REDIS_URL
```

### Q2: 任务提交成功但没有执行

**原因**: Worker 未监听对应队列

**解决**:
```bash
# 检查 Worker 监听的队列
docker logs easyrag-celery-default | grep "Consuming"

# 确保队列匹配
python celery_worker_main.py -Q default,parse,workflow,agent
```

### Q3: SSE 连接没有收到事件

**原因**: 
1. Stream Key 不匹配
2. 消费者组问题

**解决**:
```bash
# 检查 Stream 是否存在
docker exec -it easyrag-redis redis-cli KEYS "parse:*"

# 删除消费者组重新创建
docker exec -it easyrag-redis redis-cli XGROUP DESTROY parse:doc-id sse_consumers
```

### Q4: 任务重试次数过多

**原因**: 任务逻辑错误或外部依赖失败

**解决**:
```python
# 查看失败任务详情
celery -A app.core.celery_app inspect failed

# 手动重试
celery -A app.core.celery_app retry id=task-id
```

---

## 性能调优

### Worker 并发配置

```yaml
# docker-compose.celery.yml

# 文档解析队列 (IO 密集, 低并发)
celery-worker-parse:
  command: celery -A app.core.celery_app worker -Q parse -l info -n parse@%h --concurrency=2

# 工作流队列 (CPU 密集, 高并发)
celery-worker-workflow:
  command: celery -A app.core.celery_app worker -Q workflow -l info -n workflow@%h --concurrency=8

# Agent 队列 (长任务, 中等并发)
celery-worker-agent:
  command: celery -A app.core.celery_app worker -Q agent -l info -n agent@%h --concurrency=4 --prefetch-multiplier=1
```

### Redis 内存配置

```bash
# docker-compose.celery.yml
redis:
  command: redis-server --appendonly yes --maxmemory 1gb --maxmemory-policy allkeys-lru
```

### Stream 保留策略

```python
# app/core/redis_streams.py
# maxlen 控制每个 Stream 的最大条目数

await self._redis.xadd(
    stream,
    data,
    maxlen=10000,  # 最多保留 10000 条
    approximate=True
)
```

---

## 下一步

- [ ] 实际集成 parser/chunker/embedding 服务
- [ ] 添加任务优先级支持
- [ ] 实现死信队列
- [ ] 添加分布式锁
- [ ] 集成 Langfuse 追踪
- [ ] 配置 Celery Beat 定时任务
