# 后端架构演进文档

> 更新日期: 2026-09-10
> 目的: 记录后端架构的重大变化和迁移路径

---

## 架构演进历程

### Phase 1: Celery Worker（初始架构）

最初使用 Celery 处理所有异步任务：
- 文档解析：`parse_tasks.py`
- 工作流执行：`workflow_tasks.py`
- Agent 对话：`agent_tasks.py`

**问题**：
- Celery 任务难以实现复杂的流式输出
- 工作流编排受限
- Agent 对话需要 SSE 实时推送

---

### Phase 2: 混合架构（当前状态）

#### 文档解析 - Celery（仍在使用）
```
API → Celery Task (parse_tasks.py) → 解析管线
```
- ✅ 稳定运行
- ✅ 支持重试和错误处理
- ✅ 使用 Redis Streams 推送进度

#### Agent 服务 - API 直连（已迁移）
```
API → AgentService → LangGraph React Agent → SSE 流式响应
```
- ✅ 完全移除 Celery 依赖
- ✅ 支持 SSE 实时流式输出
- ✅ 更好的工具集成

**迁移路径**：
- ❌ `app/worker/tasks/agent_tasks.py`（已废弃）
- ✅ `app/services/agent_service.py`（新的实现）

#### 工作流执行 - 双轨制（迁移中）

**Celery 方式**（旧）：
```
API → celery_client.enqueue_workflow_task → Celery Task (workflow_tasks.py)
```
- ⚠️ 仍部分使用
- ⚠️ 节点执行器是占位符实现

**PGWorker 方式**（新）：
```
API → PGJobQueue.enqueue → PGWorker → GraphBuilder → LangGraph
```
- ✅ 完整的节点执行器实现
- ✅ 支持复杂工作流
- ✅ 支持中断点和调试

**迁移路径**：
- ⚠️ `app/worker/tasks/workflow_tasks.py`（已标记废弃）
- ✅ `app/worker/pg_worker.py` + `app/core/engine/`（新的实现）

---

## 核心模块迁移状态

| 模块 | 旧实现 | 新实现 | 状态 |
|------|--------|--------|------|
| **文档解析** | Celery `parse_tasks.py` | - | ✅ 稳定使用 |
| **Agent 对话** | Celery `agent_tasks.py` | `AgentService` | ✅ 已迁移 |
| **工作流执行** | Celery `workflow_tasks.py` | PGWorker + LangGraph | 🟡 迁移中 |
| **检索测试** | Celery 占位符 | PGWorker | ✅ 已迁移 |

---

## 废弃代码处理

### 已删除
- ✅ `parse_tasks_v2.py` - 被完善的 `parse_tasks.py` 替代

### 已标记废弃
- ⚠️ `agent_tasks.py` - 添加 DeprecationWarning
- ⚠️ `workflow_tasks.py` - 添加 DeprecationWarning

### 迁移建议

#### 1. Agent 相关代码
```python
# 旧方式（已废弃）
from app.worker.tasks.agent_tasks import execute_agent_chat

# 新方式（推荐）
from app.services.agent_service import AgentService
svc = AgentService()
async for event in svc.chat(agent_id, question, user_id):
    yield event
```

#### 2. 工作流执行
```python
# 旧方式（已废弃）
from app.core.engine.celery_client import enqueue_workflow_task
execution_id = await enqueue_workflow_task(workflow_id, inputs, trigger, user_id)

# 新方式（推荐）
from app.core.engine.pg_queue import PGJobQueue
job_id = await PGJobQueue.enqueue_task('workflow', {
    "workflow_id": workflow_id,
    "inputs": inputs,
    "trigger": trigger,
    "user_id": user_id
})
```

---

## 技术选型演进

### LLM/Agent 框架
- ✅ **LangChain 1.X** - 核心 LLM 抽象
- ✅ **LangGraph** - Agent 和工作流编排
- ✅ **create_react_agent** - ReAct 模式 Agent

### 任务队列
- ✅ **Celery** - 文档解析等传统异步任务
- ✅ **PostgreSQL + SKIP LOCKED** - 新的 job queue（PGWorker）
- ✅ **Redis Streams** - 事件推送

### 向量化和检索
- ✅ **pgvector** - 向量存储
- ✅ **LangChain Embeddings** - 向量化
- ✅ **Hybrid Retriever** - 混合检索

---

## 下一步计划

### 短期（1-2 周）
1. 完成工作流执行完全迁移到 PGWorker
2. 移除 `workflow_tasks.py` 和 `agent_tasks.py`
3. 更新 `celery_app.py` 的 include 列表

### 中期（1-2 月）
1. 统一任务队列为 PostgreSQL
2. 移除 Redis 依赖（仅保留缓存用途）
3. 完善 PGWorker 错误处理和重试

### 长期（3+ 月）
1. 考虑引入 Kafka 或 NATS 替代 Streams
2. 优化 LangGraph 并发性能
3. 实现工作流可视化调试工具

---

## 参考资料

- LangGraph 文档: https://langchain-ai.github.io/langgraph/
- PostgreSQL SKIP LOCKED: https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE
- 项目设计文档: `docs/backend-plans/`