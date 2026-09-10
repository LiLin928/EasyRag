# PGWorker 清理分析报告

> 分析日期: 2026-09-10
> 目的: 评估清理 PGWorker 相关代码的影响和步骤

---

## 📊 分析结果

### PGWorker 定义位置
1. `app/worker/pg_worker.py` - Worker 实现类（主文件）
2. `app/worker/pg_worker_main.py` - Worker 启动脚本
3. `app/core/engine/pg_queue.py` - PGJobQueue 实现
4. `app/core/engine/sse_bus_pg.py` - SSE 发布工具

### 使用 PGJobQueue 的地方

#### 1. API 端点（需要迁移到 Celery）
- **`app/api/v2/health.py`** - 健康检查
  - `PGJobQueue.count_pending()` - 统计待处理任务
  - `PGJobQueue.count_running()` - 统计运行中任务
  - `PGJobQueue.list_workers()` - 列出活跃 workers

- **`app/api/v2/retrieval_testing.py`** - 检索测试
  - `PGJobQueue.enqueue_task()` - 入队检索测试任务

- **`app/api/v2/webhooks.py`** - Webhook 触发
  - `PGJobQueue().enqueue()` - 入队工作流任务

#### 2. 其他使用点
- **`app/core/engine/arq_client.py`** - 已迁移到使用 PGJobQueue
  - `PGJobQueue.enqueue()` - 工作流入队
- **`app/services/document_service_v2.py`** - 示例服务（已迁移到 Celery）

### 与 Celery 的功能重叠

| 功能 | Celery Worker | PGWorker | 状态 |
|------|---------------|----------|------|
| 工作流执行 | `execute_workflow` | `_execute_workflow` | ⚠️ 重叠 |
| 检索测试 | `execute_retrieval_test` | `_execute_retrieval_test` | ⚠️ 重叠 |
| 文档解析 | `parse_document` | `_execute_parse_document` | ⚠️ 重叠 |
| Re-embed | - | `_execute_reembed_chunks` | ✅ Celery 无此功能 |

---

## 🎯 清理影响评估

### 需要迁移的功能

#### 1. 健康检查端点
**当前**: 使用 PGJobQueue 统计队列状态
**迁移到**: 使用 Celery Inspect API

```python
# 旧代码
pending = await PGJobQueue.count_pending(s)
running = await PGJobQueue.count_running(s)

# 新代码
inspect = celery_app.control.inspect()
active = inspect.active()
reserved = inspect.reserved()
```

#### 2. 检索测试入队
**当前**: `PGJobQueue.enqueue_task()`
**迁移到**: Celery 任务调用

```python
# 旧代码
await PGJobQueue.enqueue_task('retrieval_test', {"run_id": run_id})

# 新代码
from app.worker.tasks.parse_tasks import execute_retrieval_test
execute_retrieval_test.delay(run_id)
```

#### 3. Webhook 触发工作流
**当前**: `PGJobQueue().enqueue()`
**迁移到**: `celery_client.enqueue_workflow_task()`

```python
# 旧代码
queue = PGJobQueue()
job_id = await queue.enqueue("workflow", {...})

# 新代码
from app.core.engine.celery_client import enqueue_workflow_task
execution_id = await enqueue_workflow_task(workflow_id, inputs, "webhook", user_id)
```

---

## 📋 清理步骤

### 步骤 1: 迁移 API 端点（优先级：高）

1. **`health.py`** - 使用 Celery Inspect API
2. **`retrieval_testing.py`** - 使用 Celery 任务
3. **`webhooks.py`** - 使用 celery_client

### 步骤 2: 删除 PGWorker 文件（优先级：高）

删除文件：
- `app/worker/pg_worker.py`
- `app/worker/pg_worker_main.py`
- `app/core/engine/pg_queue.py`
- `app/core/engine/sse_bus_pg.py`（如果不再需要）
- `app/core/engine/arq_client.py`（已废弃）

### 步骤 3: 清理导入和引用（优先级：中）

更新 `app/worker/__init__.py` 移除 PGWorker 相关导入

### 步骤 4: 更新文档（优先级：低）

- 更新架构文档
- 移除 PGWorker 相关说明

---

## ⚠️ 风险评估

### 低风险
- ✅ 工作流执行：Celery 已有完整实现
- ✅ 检索测试：Celery 已有实现
- ✅ 文档解析：Celery 已有实现

### 中等风险
- ⚠️ Re-embed 功能：Celery 目前没有，需要添加或放弃该功能
- ⚠️ 健康检查：需要验证 Celery Inspect API 的可用性

---

## 📝 建议

### 推荐方案
1. **立即清理**：删除 PGWorker 相关代码
2. **迁移 API**：使用 Celery API 替代 PGJobQueue
3. **保留功能**：确保所有功能正常工作

### 替代方案（不推荐）
保留 PGWorker 作为备选方案，但这会增加维护负担。

---

## ✅ 清理后收益

1. **代码简化**：减少约 600 行代码
2. **架构统一**：单一任务队列系统（Celery）
3. **维护性提升**：减少重复功能
4. **部署简化**：只需管理 Celery workers

---

## 🚀 下一步行动

如果批准清理，我将：
1. 迁移 API 端点到使用 Celery
2. 删除 PGWorker 相关文件
3. 运行测试确保功能正常
4. 提交更改