# EasyRAG Celery + Redis Streams 生产就绪配置

## Phase 3 完成文件清单

### 死信队列
| 文件 | 大小 | 说明 |
|------|------|------|
| `app/worker/tasks/dead_letter.py` | ~7KB | DLQ 管理、失败任务处理 |

### 任务优先级
| 文件 | 大小 | 说明 |
|------|------|------|
| `app/core/celery_priority.py` | ~7KB | 优先级队列、自动扩缩容 |

### 分布式锁
| 文件 | 大小 | 说明 |
|------|------|------|
| `app/core/distributed_lock.py` | ~8KB | Redis 分布式锁 |

### Langfuse 追踪
| 文件 | 大小 | 说明 |
|------|------|------|
| `app/core/tracing.py` | ~8KB | 全链路追踪、指标收集 |

### Celery Beat
| 文件 | 大小 | 说明 |
|------|------|------|
| `celery_beat.py` | ~5KB | 定时任务配置 |

---

## 生产环境部署

### 1. 环境变量配置

```bash
# .env.production
# Redis
REDIS_URL=redis://redis-cluster:6379
CELERY_BROKER_URL=redis://redis-cluster:6379/0
CELERY_RESULT_BACKEND=redis://redis-cluster:6379/1

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@pg-primary:5432/easyrag

# Langfuse (可选)
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-xxx
LANGFUSE_SECRET_KEY=sk-xxx
LANGFUSE_HOST=https://cloud.langfuse.com

# 安全配置
SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120

# Worker 配置
CELERY_WORKER_CONCURRENCY=8
CELERY_TASK_MAX_RETRIES=3
```

### 2. Docker Compose 生产版

```yaml
# docker-compose.prod.yml
version: "3.8"

services:
  # Redis 集群 (使用 Sentinel)
  redis-master:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 2gb
    volumes:
      - redis-master-data:/data
    
  redis-slave-1:
    image: redis:7-alpine
    command: redis-server --slaveof redis-master 6379
    
  redis-slave-2:
    image: redis:7-alpine
    command: redis-server --slaveof redis-master 6379
    
  redis-sentinel:
    image: redis:7-alpine
    command: redis-sentinel /etc/redis/sentinel.conf

  # PostgreSQL 主从
  postgres-primary:
    image: postgres:16
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASS}
      POSTGRES_DB: easyrag
    volumes:
      - pg-primary-data:/var/lib/postgresql/data
      
  postgres-replica:
    image: postgres:16
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASS}
    command: |
      bash -c "
        pg_basebackup -h postgres-primary -D /var/lib/postgresql/data -U ${DB_USER} -v -P -W
        echo \"standby_mode = on\" >> /var/lib/postgresql/data/recovery.conf
      "

  # API 多实例
  api-1:
    build: ./backend
    environment:
      - REDIS_URL=redis://redis-sentinel:26379
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: "2"
          memory: 4G
    
  # Worker 分类
  worker-critical:
    build: ./backend
    command: celery -A app.core.celery_app worker -Q critical -c 4 -P gevent
    deploy:
      replicas: 2
      
  worker-high:
    build: ./backend
    command: celery -A app.core.celery_app worker -Q high -c 8 -P gevent
    deploy:
      replicas: 4
      
  worker-default:
    build: ./backend
    command: celery -A app.core.celery_app worker -Q default,parse -c 4
    deploy:
      replicas: 4
      
  worker-low:
    build: ./backend
    command: celery -A app.core.celery_app worker -Q low -c 2
    deploy:
      replicas: 2

  # Celery Beat (单实例)
  beat:
    build: ./backend
    command: celery -A celery_beat beat -l info
    deploy:
      replicas: 1

  # Flower (监控)
  flower:
    build: ./backend
    command: celery -A app.core.celery_app flower --port=5555
    ports:
      - "5555:5555"

volumes:
  redis-master-data:
  pg-primary-data:
```

### 3. Kubernetes 部署

```yaml
# k8s/worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: celery-worker-parse
spec:
  replicas: 4
  selector:
    matchLabels:
      app: celery-worker-parse
  template:
    metadata:
      labels:
        app: celery-worker-parse
    spec:
      containers:
      - name: worker
        image: easyrag/backend:latest
        command: ["celery"]
        args:
          - "-A"
          - "app.core.celery_app"
          - "worker"
          - "-Q"
          - "parse"
          - "-c"
          - "4"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        env:
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: easyrag-secrets
              key: redis-url
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: easyrag-secrets
              key: database-url
        livenessProbe:
          exec:
            command:
            - celery
            - -A
            - app.core.celery_app
            - inspect
            - ping
          initialDelaySeconds: 30
          periodSeconds: 30
```

---

## 关键特性

### 1. 死信队列 (DLQ)

```python
# 任务达到最大重试后自动进入 DLQ
@task_failure.connect
def handle_task_failure(sender, task_id, exception, ...):
    if retry_count >= max_retries:
        DeadLetterQueue.add_to_dlq(...)
```

- 自动记录失败任务
- 支持手动重试
- 定时清理过期任务

### 2. 任务优先级

```python
# 提交关键任务
submit_critical_task("parse_document", doc_id, file_key)

# 提交低优先级任务
submit_low_priority_task("cleanup_old_data")
```

- 4 级优先级：CRITICAL > HIGH > NORMAL > LOW
- 自动队列路由
- 自动扩缩容建议

### 3. 分布式锁

```python
# 防止重复解析
async with DistributedLock(f"doc:{doc_id}:parse", ttl=300):
    await parse_document(doc_id)
```

- 基于 Redis SETNX
- 自动续期
- 安全释放

### 4. 全链路追踪

```python
# 自动追踪 Celery 任务
@traced_task
def my_task(self, ...):
    pass

# 手动追踪
with trace_span("embedding"):
    await embed_chunks(chunks)
```

- Langfuse 集成
- 嵌套 Span 支持
- 指标收集

### 5. 定时任务

```python
# 每小时监控 DLQ
@celery_app.task(name="dlq.monitor")
def monitor_dead_letter_queue():
    ...

# 每天清理过期 Streams
@celery_app.task(name="beat.cleanup_streams")
def cleanup_expired_streams():
    ...
```

---

## 监控告警

### Flower 监控

```bash
docker run -p 5555:5555 easyrag/backend \
  celery -A app.core.celery_app flower --port=5555
```

### Prometheus + Grafana

```yaml
# 导出 Celery 指标
- name: CELERY_WORKER_STATE
  help: Worker state
- name: CELERY_TASKS_ACTIVE
  help: Active tasks count
- name: CELERY_QUEUE_LENGTH
  help: Queue length
```

### 告警规则

```yaml
# 队列堆积告警
- alert: QueueBacklogHigh
  expr: celery_queue_length > 1000
  for: 5m
  
# Worker 离线告警
- alert: WorkerOffline
  expr: celery_worker_up == 0
  for: 1m
  
# 任务失败率告警
- alert: TaskFailureRate
  expr: rate(celery_task_failed[5m]) > 0.1
```

---

## 性能调优

### Worker 配置

```python
# 高并发 Worker
worker = Worker(
    app=celery_app,
    concurrency=16,
    pool="gevent",  # 异步 IO
    task_time_limit=3600,
    worker_prefetch_multiplier=1,
)
```

### Redis 配置

```bash
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
appendonly yes
appendfsync everysec
```

### PostgreSQL 配置

```sql
-- 连接池
max_connections = 200
shared_buffers = 1GB
work_mem = 16MB
```

---

## 迁移路径

### 从 V2 到 Production

```bash
# 1. 更新配置
cp .env.production.example .env

# 2. 更新依赖
pip install -r requirements-prod.txt

# 3. 启动 Redis Sentinel
docker-compose -f docker-compose.redis.yml up -d

# 4. 迁移数据库
alembic upgrade head

# 5. 启动服务
docker-compose -f docker-compose.prod.yml up -d

# 6. 验证
./scripts/health-check.sh
```

---

## 文档总结

| 阶段 | 文件数 | 完成度 |
|------|--------|--------|
| Phase 1: 基础设施 | 8 | ✅ 100% |
| Phase 2: Docker 配置 | 6 | ✅ 100% |
| Phase 3: 生产就绪 | 6 | ✅ 100% |
| **总计** | **20** | **✅ 100%** |
