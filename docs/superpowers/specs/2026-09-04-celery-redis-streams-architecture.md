# EasyRAG Celery + Redis Streams 混合架构设计

> **版本**: V1.0
> **日期**: 2026-09-04
> **状态**: 设计方案
> **文档定位**: 任务队列与事件总线架构升级方案

---

## 一、设计目标

基于 Dify 演进经验，设计 **Celery + Redis Streams 双轨混合架构**：

| 组件 | 职责 | 选型理由 |
|------|------|---------|
| **Celery + Redis** | 任务队列 | 成熟可靠，支持重试/定时任务/监控 |
| **Redis Streams** | 事件总线 | 低延迟流式推送，原生支持消费者组 |

**核心原则**: 任务调度与事件推送分离，各司其职。

---

## 二、当前架构 vs 目标架构

### 2.1 当前 PostgreSQL 架构

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   HTTP API  │────►│  PGJobQueue  │────►│  PG Worker  │
│             │     │  (enqueue)   │     │ (SKIP LOCKED)│
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                │
                        ┌───────────────────────┘
                        ▼
               ┌────────────────┐
               │  PostgreSQL    │
               │  execution_    │
               │  events (SSE)  │
               └────────┬───────┘
                        │
                        ▼
               ┌────────────────┐
               │  SSE Consumer  │
               │  (前端订阅)     │
               └────────────────┘
```

**问题**:
- PG 队列无重试机制，任务失败需自建
- SSE 轮询或 LISTEN/NOTIFY 延迟较高
- 横向扩展受限

### 2.2 目标混合架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                              前端层                                  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           FastAPI 应用层                             │
│                                                                      │
│   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐   │
│   │   任务提交 API   │   │   事件订阅 API   │   │   状态查询 API   │   │
│   └────────┬────────┘   └────────┬────────┘   └─────────────────┘   │
│            │                    │                                   │
│            ▼ Redis Queue        ▼ Redis Streams                    │
│   ┌─────────────────┐       ┌─────────────────┐                      │
│   │  Celery Task    │       │  Event Stream   │                      │
│   │  (enqueue)      │       │  (XADD)         │                      │
│   └─────────────────┘       └─────────────────┘                      │
└─────────────────────────────────────────────────────────────────────┘
             │                       │
             ▼                       ▼
┌─────────────────────┐       ┌─────────────────────┐
│   Celery Worker      │       │  Event Consumer     │
│   (celery -A worker) │       │  (XREADGROUP)       │
│                      │       │                     │
│  ┌──────────────┐   │       │  ┌─────────────┐    │
│  │ 任务完成事件  │───┼───────►│  │ publish()   │    │
│  │ publish()    │   │       │  │ to SSE      │    │
│  └──────────────┘   │       │  └─────────────┘    │
└─────────────────────┘       └─────────────────────┘
```

**优势**:
- Celery 提供任务重试、死信队列、定时任务
- Streams 提供低延迟流式推送（<10ms）
- 天然支持多 Worker 扩展

---

## 三、组件设计

### 3.1 Celery 任务队列

```python
# app/core/celery_app.py
from celery import Celery

app = Celery(
    "easyrag",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

# 任务分类队列
app.conf.task_routes = {
    "parse.*": {"queue": "parse"},
    "workflow.*": {"queue": "workflow"},
    "agent.*": {"queue": "agent"},
}
```

**任务类型**:

| 任务 | 队列 | 特性 |
|------|------|------|
| `parse_document` | parse | 可重试，超时 5min |
| `execute_workflow` | workflow | 支持 chain/group |
| `execute_agent` | agent | 长时间运行，ACK |

### 3.2 Redis Streams 事件总线

```python
# app/core/redis_streams.py
class EventBus:
    async def publish(self, stream: str, event: Event) -> str:
        """XADD 发布事件"""
        return await redis.xadd(
            stream,
            {"type": event.type, "payload": json.dumps(event.payload)},
            maxlen=10000,
            approximate=True
        )
    
    async def subscribe(self, streams: list[str]) -> AsyncGenerator[Event]:
        """XREADGROUP 订阅事件"""
        async for msg in redis.xreadgroup(
            groupname="sse_consumers",
            streams={s: ">" for s in streams},
            block=5000,
        ):
            yield parse_event(msg)
            await redis.xack(stream, "sse_consumers", msg.id)
```

**事件流分类**:

| Stream Key | 用途 | 保留策略 |
|------------|------|---------|
| `parse:{doc_id}` | 文档解析进度 | 10000条 |
| `workflow:{exec_id}` | 工作流状态 | 10000条 |
| `agent:{chat_id}` | Agent Token 流 | 1000条 |

---

## 四、代码结构

```
backend/
├── app/
│   ├── core/
│   │   ├── celery_app.py          # Celery 配置
│   │   └── redis_streams.py       # Streams 封装
│   │
│   ├── worker/
│   │   ├── celery_worker.py       # Celery Worker 入口
│   │   └── tasks/
│   │       ├── parse_tasks.py     # 文档解析任务
│   │       ├── workflow_tasks.py  # 工作流任务
│   │       └── agent_tasks.py     # Agent 任务
│   │
│   └── api/v2/
│       └── sse.py                 # SSE 端点（Streams版）
│
├── celeryconfig.py               # Celery 配置
└── celery_worker_main.py         # Worker 启动脚本
```

---

## 五、关键决策

### 5.1 为什么不是纯 Celery？

| 场景 | Celery | Streams | 结论 |
|------|--------|---------|------|
| Token 流式输出 | 高延迟（>100ms） | 低延迟（<10ms） | Streams 更优 |
| 前端实时进度 | 需轮询 | 直接推送 | Streams 更优 |
| 任务重试 | 内置完善 | 需自建 | Celery 更优 |

### 5.2 为什么不是纯 Streams？

- 无内置重试机制
- 无死信队列
- 无定时任务支持
- 任务调度逻辑需自建

### 5.3 为什么从 PostgreSQL 迁移？

| 特性 | PostgreSQL | Redis |
|------|-----------|-------|
| 任务重试 | ❌ 需自建 | ✅ Celery 内置 |
| 流式推送 | ❌ 轮询/LISTEN | ✅ 原生支持 |
| 扩展性 | ❌ SKIP LOCKED 瓶颈 | ✅ 无锁消费 |
| 监控 | ❌ 需自建 | ✅ Flower |

---

## 六、迁移路径

### Phase 1: 基础设施（1-2天）

```bash
# 1. 添加依赖
pip install celery[redis] redis

# 2. 配置 Celery
# app/core/celery_app.py

# 3. 配置 Streams
# app/core/redis_streams.py
```

### Phase 2: 服务层改造（3-5天）

1. **文档解析**: PGQueue → Celery
2. **工作流执行**: 同步执行 → Celery Chain
3. **SSE 总线**: PG 事件 → Streams

### Phase 3: 验证与上线（2天）

```bash
# 启动 Worker
python -m celery -A app.core.celery_app worker -Q default,parse,workflow,agent -l info

# 启动应用
uvicorn app.main:app --reload
```

---

## 七、参考实现

### 7.1 发布任务

```python
# 旧: PGJobQueue.enqueue_task("parse_document", {...})
# 新:
celery_app.send_task(
    "parse_document",
    args=[doc_id, file_key],
    queue="parse",
    countdown=0,
)
```

### 7.2 发布事件

```python
# 在 Celery 任务中
@app.task(bind=True)
def parse_document(self, doc_id: int):
    # 进度更新
    asyncio.run(publish_event(
        f"parse:{doc_id}",
        "progress",
        {"pct": 50}
    ))
```

### 7.3 SSE 订阅

```python
@router.get("/parse-tasks/{doc_id}/stream")
async def stream_parse(doc_id: int):
    async def generator():
        async for stream, event in event_bus.subscribe([f"parse:{doc_id}"]):
            yield f"data: {json.dumps(event.payload)}\\n\\n"
    
    return StreamingResponse(generator(), media_type="text/event-stream")
```

---

## 八、注意事项

1. **内存管理**: Streams 设置 `maxlen` 防止内存无限增长
2. **ACK 机制**: 消费者需手动 ACK，避免消息丢失
3. **连接池**: Redis 连接需合理复用
4. **错误处理**: Celery 任务失败时需发布错误事件到 Streams

---

## 附录：对比总结

| 维度 | PG Queue | Celery + Streams |
|------|---------|------------------|
| 架构复杂度 | 低 | 中 |
| 延迟 | 高 | 低 |
| 可靠性 | 中 | 高 |
| 扩展性 | 中 | 高 |
| 监控 | 需自建 | Flower + Redis CLI |
| 学习成本 | 低 | 中 |

---

*文档结束*
