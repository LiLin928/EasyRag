# MinIO 存储集成与 Prometheus 监控实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 EasyRAG 后端的文件存储统一切换到 MinIO，并集成 Prometheus 监控系统，实现全维度可观测性。

**Architecture:** 分两个阶段实施：第一阶段完成存储切换（MinIO 启用 + 健康检查），第二阶段集成 Prometheus 监控（三层指标采集 + Grafana 仪表板 + AlertManager 告警）。使用装饰器模式最小化代码侵入。

**Tech Stack:** FastAPI, MinIO Python SDK, Prometheus Client, prometheus-fastapi-instrumentator, Grafana, AlertManager

---

## 文件结构总览

### 新建文件
```
backend/app/core/metrics/
├── __init__.py                      # 导出所有指标类
├── app_metrics.py                   # 应用层指标（prometheus-fastapi-instrumentator）
├── storage_metrics.py               # 存储层指标（自定义装饰器）
└── business_metrics.py              # 业务层指标（自定义工具类）

backend/app/core/storage/
└── health.py                        # 存储健康检查

backend/deploy/prometheus/
├── prometheus.yml                   # Prometheus 配置
├── alertmanager.yml                 # AlertManager 配置
├── alerts/
│   ├── app_alerts.yml              # 应用层告警规则
│   ├── storage_alerts.yml          # 存储层告警规则
│   └── business_alerts.yml         # 业务层告警规则
└── grafana/
    ├── dashboards/
    │   ├── app-overview.json       # 应用概览仪表板
    │   ├── storage-details.json    # 存储详情仪表板
    │   └── business-metrics.json   # 业务指标仪表板
    ├── datasources/
    │   └── prometheus.yml          # Prometheus 数据源配置
    └── dashboard.yml               # 仪表板自动加载配置

backend/deploy/
└── docker-compose.monitoring.yml    # 监控栈 Docker Compose

backend/tests/
└── test_metrics.py                  # 指标采集单元测试
```

### 修改文件
```
backend/app/providers/storage/factory.py              # 统一调用 core.storage 工厂
backend/app/core/storage/minio.py                     # 添加指标装饰器
backend/app/core/storage/local.py                     # 添加指标装饰器
backend/app/config.py                                 # 添加 Prometheus 配置项
backend/app/main.py                                   # 注册 Prometheus 中间件
backend/pyproject.toml                                # 添加 prometheus 依赖
backend/.env.example                                  # 添加配置示例
```

---

## Phase 1: 存储切换（MinIO 启用）

### Task 1: 添加 Prometheus 依赖

**Files:**
- Modify: `backend/pyproject.toml:dependencies`

- [ ] **Step 1: 修改 pyproject.toml 添加 Prometheus 依赖**

```toml
dependencies = [
  # ... 现有依赖 ...

  # Prometheus 监控
  "prometheus-client>=0.19.0",
  "prometheus-fastapi-instrumentator>=7.0.0",
]

[project.optional-dependencies]
monitoring = [
  "prometheus-client>=0.19.0",
  "prometheus-fastapi-instrumentator>=7.0.0",
]
```

- [ ] **Step 2: 运行 uv sync 安装依赖**

```bash
cd backend
uv sync
```

Expected: 依赖安装成功，无错误

- [ ] **Step 3: 验证依赖安装**

```bash
uv run python -c "import prometheus_client; import prometheus_fastapi_instrumentator; print('Prometheus dependencies installed')"
```

Expected: 输出 "Prometheus dependencies installed"

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "feat: add Prometheus monitoring dependencies

- Add prometheus-client>=0.19.0
- Add prometheus-fastapi-instrumentator>=7.0.0
- Add monitoring optional dependency group

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 2: 扩展配置管理

**Files:**
- Modify: `backend/app/config.py:Settings`
- Modify: `backend/.env.example`

- [ ] **Step 1: 扩展 Settings 配置类**

在 `backend/app/config.py` 的 `Settings` 类中添加：

```python
    # 对象存储（本地 FS → MinIO）
    storage_type: str = "local"        # local | minio
    storage_local_dir: str = "uploads"  # 本地存储目录
    # MinIO 配置
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "easyrag"
    minio_secure: bool = False
    minio_public_url: str | None = None

    # Prometheus 监控
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    prometheus_scrape_interval: int = 15

    # 指标标签
    metrics_namespace: str = "easyrag"
    metrics_environment: str = "development"
```

注意：检查配置是否已存在（storage_type 和 minio_* 配置可能已存在），如果存在则跳过重复添加，只添加 Prometheus 相关配置。

- [ ] **Step 2: 更新 .env.example 添加配置示例**

在 `backend/.env.example` 末尾添加：

```bash
# Prometheus 监控配置
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090
PROMETHEUS_SCRAPE_INTERVAL=15

# 指标标签配置
METRICS_NAMESPACE=easyrag
METRICS_ENVIRONMENT=development
```

注意：检查 `.env.example` 是否已有 `STORAGE_TYPE` 和 `MINIO_*` 配置，如果有则跳过。

- [ ] **Step 3: 验证配置加载**

```bash
cd backend
uv run python -c "from app.config import settings; print(f'prometheus_enabled={settings.prometheus_enabled}, metrics_namespace={settings.metrics_namespace}')"
```

Expected: 输出 `prometheus_enabled=True, metrics_namespace=easyrag`

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py backend/.env.example
git commit -m "feat: add Prometheus monitoring configuration

- Add prometheus_enabled, prometheus_port, prometheus_scrape_interval
- Add metrics_namespace and metrics_environment labels
- Update .env.example with monitoring config examples

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 3: 修改存储工厂

**Files:**
- Modify: `backend/app/providers/storage/factory.py`

- [ ] **Step 1: 读取当前工厂代码**

```bash
cat backend/app/providers/storage/factory.py
```

Expected: 看到当前的 `get_storage()` 函数实现

- [ ] **Step 2: 修改工厂函数调用 core.storage**

将 `backend/app/providers/storage/factory.py` 内容替换为：

```python
"""对象存储工厂，按 settings.storage_type 选择实现。"""
from app.core.storage import get_storage as core_get_storage


def get_storage():
    """返回配置的对象存储实例（local | minio）。

    统一调用 app.core.storage 工厂，支持本地文件系统和 MinIO。
    """
    return core_get_storage()
```

- [ ] **Step 3: 验证工厂修改**

```bash
cd backend
uv run python -c "from app.providers.storage.factory import get_storage; storage = get_storage(); print(f'Storage type: {type(storage).__name__}')"
```

Expected: 根据配置输出 `LocalStorage` 或 `MinioStorage`

- [ ] **Step 4: Commit**

```bash
git add backend/app/providers/storage/factory.py
git commit -m "feat: unify storage factory to use core.storage

- Replace old factory implementation with call to core.storage
- Remove duplicate MinIO implementation code
- Ensure all consumers use unified storage interface

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 4: 创建存储健康检查

**Files:**
- Create: `backend/app/core/storage/health.py`
- Modify: `backend/app/api/v2/health.py`（如果存在健康检查端点）

- [ ] **Step 1: 创建健康检查模块**

创建 `backend/app/core/storage/health.py`：

```python
"""存储健康检查。"""
from app.core.storage import get_storage
from app.config import settings


async def check_storage_health() -> dict:
    """检查存储系统健康状态。

    Returns:
        健康状态字典，包含：
        - status: healthy / unhealthy
        - storage_type: local / minio
        - details: 详细信息
    """
    try:
        storage = get_storage()

        if settings.storage_type == "minio":
            # 测试 MinIO 连接：尝试列出一个不存在的对象
            await storage.list_objects(prefix="__health_check__")

            return {
                "status": "healthy",
                "storage_type": "minio",
                "details": {
                    "endpoint": settings.minio_endpoint,
                    "bucket": settings.minio_bucket,
                }
            }
        else:
            return {
                "status": "healthy",
                "storage_type": "local",
                "details": {
                    "base_dir": settings.storage_local_dir,
                }
            }

    except Exception as e:
        return {
            "status": "unhealthy",
            "storage_type": settings.storage_type,
            "error": str(e)
        }
```

- [ ] **Step 2: 检查是否存在健康检查端点**

```bash
ls backend/app/api/v2/health.py
```

Expected: 文件存在或不存在。如果存在，需要在健康检查端点中集成存储健康检查。

- [ ] **Step 3: 集成健康检查到 API（如果端点存在）**

如果 `backend/app/api/v2/health.py` 存在，读取并修改：

```bash
cat backend/app/api/v2/health.py
```

在健康检查响应中添加存储状态。如果不存在，跳过此步骤。

- [ ] **Step 4: 测试健康检查**

```bash
cd backend
uv run python -c "
import asyncio
from app.core.storage.health import check_storage_health

result = asyncio.run(check_storage_health())
print(f'Storage health: {result}')
"
```

Expected: 输出存储健康状态，`status` 为 `healthy` 或 `unhealthy`

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/storage/health.py
git commit -m "feat: add storage health check module

- Create check_storage_health function
- Support both local and MinIO storage health checks
- Provide detailed error information when unhealthy

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 5: 测试存储切换

**Files:**
- Test: `backend/tests/test_storage.py`（已存在）

- [ ] **Step 1: 运行现有存储测试**

```bash
cd backend
uv run pytest tests/test_storage.py -v
```

Expected: 所有测试通过

- [ ] **Step 2: 测试 MinIO 连接（需要配置 STORAGE_TYPE=minio）**

修改 `.env` 或临时设置环境变量：

```bash
cd backend
STORAGE_TYPE=minio uv run python -c "
from app.core.storage import get_storage
import asyncio

storage = get_storage()
print(f'Storage type: {type(storage).__name__}')

# 测试上传
async def test():
    result = await storage.upload('test/test.txt', b'hello world')
    print(f'Upload result: {result}')

    # 测试下载
    data = await storage.download('test/test.txt')
    print(f'Download data: {data}')

    # 测试删除
    await storage.delete('test/test.txt')
    print('Delete success')

asyncio.run(test())
"
```

Expected: 输出 MinIO 操作成功

- [ ] **Step 3: Commit（如果有修改）**

```bash
git add -A
git commit -m "test: verify MinIO storage integration

- Run existing storage tests
- Test MinIO upload/download/delete operations
- Verify storage factory unification

Co-Authored-By: lilin <565387073@qq.com>"
```

---

## Phase 2: Prometheus 监控集成

### Task 6: 创建应用层指标采集

**Files:**
- Create: `backend/app/core/metrics/__init__.py`
- Create: `backend/app/core/metrics/app_metrics.py`

- [ ] **Step 1: 创建 metrics 模块目录**

```bash
mkdir -p backend/app/core/metrics
```

- [ ] **Step 2: 创建 __init__.py**

创建 `backend/app/core/metrics/__init__.py`：

```python
"""指标采集模块。

提供三层指标采集：
- 应用层：HTTP 请求、延迟、错误率
- 存储层：MinIO 操作统计
- 业务层：文档解析、工作流、Agent 对话
"""
from app.core.metrics.app_metrics import setup_app_metrics

__all__ = ["setup_app_metrics"]
```

- [ ] **Step 3: 创建应用层指标模块**

创建 `backend/app/core/metrics/app_metrics.py`：

```python
"""应用层指标采集。

使用 prometheus-fastapi-instrumentator 自动采集 HTTP 指标。
"""
from prometheus_fastapi_instrumentator import Instrumentator
from app.config import settings


def setup_app_metrics(app):
    """配置 FastAPI 应用指标采集。

    Args:
        app: FastAPI 应用实例
    """
    if not settings.prometheus_enabled:
        return

    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        env_var_name="PROMETHEUS_ENABLED",
    )

    instrumentator.instrument(app).expose(app)
```

- [ ] **Step 4: 验证应用层指标模块**

```bash
cd backend
uv run python -c "from app.core.metrics.app_metrics import setup_app_metrics; print('App metrics module loaded')"
```

Expected: 输出 "App metrics module loaded"

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/metrics/
git commit -m "feat: create application-level metrics collection

- Create metrics module structure
- Implement setup_app_metrics using prometheus-fastapi-instrumentator
- Support PROMETHEUS_ENABLED environment variable toggle

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 7: 创建存储层指标采集

**Files:**
- Modify: `backend/app/core/metrics/__init__.py`
- Create: `backend/app/core/metrics/storage_metrics.py`

- [ ] **Step 1: 创建存储层指标模块**

创建 `backend/app/core/metrics/storage_metrics.py`：

```python
"""存储层指标采集。"""
from prometheus_client import Counter, Histogram, Gauge
from functools import wraps
import time

from app.config import settings

# 指标定义
STORAGE_OPERATIONS_TOTAL = Counter(
    f"{settings.metrics_namespace}_storage_operations_total",
    "Total storage operations",
    ["operation", "status"]
)

STORAGE_OPERATION_DURATION = Histogram(
    f"{settings.metrics_namespace}_storage_operation_duration_seconds",
    "Storage operation duration in seconds",
    ["operation"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]
)

STORAGE_BYTES_TRANSFERRED = Counter(
    f"{settings.metrics_namespace}_storage_bytes_transferred_total",
    "Total bytes transferred",
    ["operation", "direction"]
)

STORAGE_ACTIVE_OPERATIONS = Gauge(
    f"{settings.metrics_namespace}_storage_active_operations",
    "Number of active storage operations",
    ["operation"]
)


class StorageMetrics:
    """存储指标采集装饰器。"""

    @staticmethod
    def track_operation(operation: str):
        """跟踪存储操作。

        Args:
            operation: 操作类型（upload, download, delete, exists, copy, list）

        Returns:
            装饰器函数
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # 增加活跃操作数
                STORAGE_ACTIVE_OPERATIONS.labels(operation=operation).inc()

                # 记录开始时间
                start_time = time.time()
                status = "success"

                try:
                    result = await func(*args, **kwargs)

                    # 记录传输字节数（仅 upload/download）
                    if operation in ["upload", "download"]:
                        if operation == "upload":
                            # 获取上传内容大小
                            bytes_count = len(kwargs.get("content", args[1] if len(args) > 1 else b""))
                            STORAGE_BYTES_TRANSFERRED.labels(
                                operation=operation,
                                direction="in"
                            ).inc(bytes_count)
                        elif operation == "download":
                            STORAGE_BYTES_TRANSFERRED.labels(
                                operation=operation,
                                direction="out"
                            ).inc(len(result))

                    return result

                except Exception as e:
                    status = "error"
                    raise

                finally:
                    # 记录操作次数
                    STORAGE_OPERATIONS_TOTAL.labels(
                        operation=operation,
                        status=status
                    ).inc()

                    # 记录操作延迟
                    duration = time.time() - start_time
                    STORAGE_OPERATION_DURATION.labels(
                        operation=operation
                    ).observe(duration)

                    # 减少活跃操作数
                    STORAGE_ACTIVE_OPERATIONS.labels(operation=operation).dec()

            return wrapper
        return decorator
```

- [ ] **Step 2: 更新 __init__.py 导出**

更新 `backend/app/core/metrics/__init__.py`：

```python
"""指标采集模块。

提供三层指标采集：
- 应用层：HTTP 请求、延迟、错误率
- 存储层：MinIO 操作统计
- 业务层：文档解析、工作流、Agent 对话
"""
from app.core.metrics.app_metrics import setup_app_metrics
from app.core.metrics.storage_metrics import StorageMetrics

__all__ = ["setup_app_metrics", "StorageMetrics"]
```

- [ ] **Step 3: 验证存储层指标模块**

```bash
cd backend
uv run python -c "from app.core.metrics.storage_metrics import StorageMetrics; print('Storage metrics module loaded')"
```

Expected: 输出 "Storage metrics module loaded"

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/metrics/
git commit -m "feat: create storage-level metrics collection

- Implement StorageMetrics decorator for tracking storage operations
- Track operation count, duration, bytes transferred, and active operations
- Use prometheus_client Counter, Histogram, and Gauge
- Support all storage operations: upload, download, delete, exists, copy, list

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 8: 创建业务层指标采集

**Files:**
- Modify: `backend/app/core/metrics/__init__.py`
- Create: `backend/app/core/metrics/business_metrics.py`

- [ ] **Step 1: 创建业务层指标模块**

创建 `backend/app/core/metrics/business_metrics.py`：

```python
"""业务层指标采集。"""
from prometheus_client import Counter, Histogram
from app.config import settings

# 文档解析指标
PARSE_DOCUMENTS_TOTAL = Counter(
    f"{settings.metrics_namespace}_parse_documents_total",
    "Total documents parsed",
    ["status"]
)

PARSE_DOCUMENT_DURATION = Histogram(
    f"{settings.metrics_namespace}_parse_document_duration_seconds",
    "Document parsing duration in seconds",
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)

PARSE_CHUNKS_CREATED_TOTAL = Counter(
    f"{settings.metrics_namespace}_parse_chunks_created_total",
    "Total chunks created during parsing"
)

# 工作流指标
WORKFLOW_EXECUTIONS_TOTAL = Counter(
    f"{settings.metrics_namespace}_workflow_executions_total",
    "Total workflow executions",
    ["workflow_id", "status"]
)

WORKFLOW_EXECUTION_DURATION = Histogram(
    f"{settings.metrics_namespace}_workflow_execution_duration_seconds",
    "Workflow execution duration in seconds",
    ["workflow_id"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)

WORKFLOW_STEPS_TOTAL = Counter(
    f"{settings.metrics_namespace}_workflow_steps_total",
    "Total workflow steps executed",
    ["step_type", "status"]
)

# Agent 指标
AGENT_CONVERSATIONS_TOTAL = Counter(
    f"{settings.metrics_namespace}_agent_conversations_total",
    "Total agent conversations",
    ["agent_id"]
)

AGENT_MESSAGES_TOTAL = Counter(
    f"{settings.metrics_namespace}_agent_messages_total",
    "Total agent messages",
    ["type"]  # user, assistant
)

AGENT_TOOL_CALLS_TOTAL = Counter(
    f"{settings.metrics_namespace}_agent_tool_calls_total",
    "Total agent tool calls",
    ["tool_name", "status"]
)

# 检索测试指标
RETRIEVAL_TESTS_TOTAL = Counter(
    f"{settings.metrics_namespace}_retrieval_tests_total",
    "Total retrieval tests",
    ["status"]
)

RETRIEVAL_TEST_DURATION = Histogram(
    f"{settings.metrics_namespace}_retrieval_test_duration_seconds",
    "Retrieval test duration in seconds",
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0]
)


class BusinessMetrics:
    """业务指标记录工具类。"""

    @staticmethod
    def record_parse(status: str, duration: float, chunks_count: int = 0):
        """记录解析任务。

        Args:
            status: 解析状态（success, failed, partial）
            duration: 解析耗时（秒）
            chunks_count: 生成的 chunk 数量
        """
        PARSE_DOCUMENTS_TOTAL.labels(status=status).inc()
        PARSE_DOCUMENT_DURATION.observe(duration)
        if chunks_count > 0:
            PARSE_CHUNKS_CREATED_TOTAL.inc(chunks_count)

    @staticmethod
    def record_workflow(workflow_id: str, status: str, duration: float = 0):
        """记录工作流执行。

        Args:
            workflow_id: 工作流 ID
            status: 执行状态（success, failed, running）
            duration: 执行耗时（秒，可选）
        """
        WORKFLOW_EXECUTIONS_TOTAL.labels(
            workflow_id=workflow_id,
            status=status
        ).inc()
        if duration > 0:
            WORKFLOW_EXECUTION_DURATION.labels(
                workflow_id=workflow_id
            ).observe(duration)

    @staticmethod
    def record_workflow_step(step_type: str, status: str):
        """记录工作流步骤。

        Args:
            step_type: 步骤类型
            status: 执行状态
        """
        WORKFLOW_STEPS_TOTAL.labels(
            step_type=step_type,
            status=status
        ).inc()

    @staticmethod
    def record_agent_conversation(agent_id: str):
        """记录 Agent 对话。

        Args:
            agent_id: Agent ID
        """
        AGENT_CONVERSATIONS_TOTAL.labels(agent_id=agent_id).inc()

    @staticmethod
    def record_agent_message(message_type: str):
        """记录 Agent 消息。

        Args:
            message_type: 消息类型（user, assistant）
        """
        AGENT_MESSAGES_TOTAL.labels(type=message_type).inc()

    @staticmethod
    def record_agent_tool_call(tool_name: str, status: str):
        """记录 Agent 工具调用。

        Args:
            tool_name: 工具名称
            status: 调用状态（success, error）
        """
        AGENT_TOOL_CALLS_TOTAL.labels(
            tool_name=tool_name,
            status=status
        ).inc()

    @staticmethod
    def record_retrieval_test(status: str, duration: float = 0):
        """记录检索测试。

        Args:
            status: 测试状态（success, failed, timeout）
            duration: 测试耗时（秒，可选）
        """
        RETRIEVAL_TESTS_TOTAL.labels(status=status).inc()
        if duration > 0:
            RETRIEVAL_TEST_DURATION.observe(duration)
```

- [ ] **Step 2: 更新 __init__.py 导出**

更新 `backend/app/core/metrics/__init__.py`：

```python
"""指标采集模块。

提供三层指标采集：
- 应用层：HTTP 请求、延迟、错误率
- 存储层：MinIO 操作统计
- 业务层：文档解析、工作流、Agent 对话
"""
from app.core.metrics.app_metrics import setup_app_metrics
from app.core.metrics.storage_metrics import StorageMetrics
from app.core.metrics.business_metrics import BusinessMetrics

__all__ = ["setup_app_metrics", "StorageMetrics", "BusinessMetrics"]
```

- [ ] **Step 3: 验证业务层指标模块**

```bash
cd backend
uv run python -c "from app.core.metrics.business_metrics import BusinessMetrics; print('Business metrics module loaded')"
```

Expected: 输出 "Business metrics module loaded"

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/metrics/
git commit -m "feat: create business-level metrics collection

- Implement BusinessMetrics for tracking business operations
- Track document parsing: count, duration, chunks created
- Track workflow executions: count, duration, steps
- Track agent conversations: count, messages, tool calls
- Track retrieval tests: count, duration
- Use prometheus_client Counter and Histogram

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 9: 集成存储层指标到 MinIO

**Files:**
- Modify: `backend/app/core/storage/minio.py`

- [ ] **Step 1: 读取 MinIO 存储实现**

```bash
head -50 backend/app/core/storage/minio.py
```

Expected: 看到导入部分和 MinioStorage 类定义

- [ ] **Step 2: 添加指标装饰器导入**

在 `backend/app/core/storage/minio.py` 文件顶部导入部分添加：

```python
from app.core.metrics.storage_metrics import StorageMetrics
```

- [ ] **Step 3: 为 upload 方法添加装饰器**

找到 `upload` 方法定义，在方法上方添加装饰器：

```python
    @StorageMetrics.track_operation("upload")
    async def upload(
        self,
        key: str,
        content: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """上传文件到 MinIO。"""
        # ... 原有实现保持不变 ...
```

- [ ] **Step 4: 为 download 方法添加装饰器**

```python
    @StorageMetrics.track_operation("download")
    async def download(self, key: str) -> bytes:
        """从 MinIO 下载文件。"""
        # ... 原有实现保持不变 ...
```

- [ ] **Step 5: 为 delete 方法添加装饰器**

```python
    @StorageMetrics.track_operation("delete")
    async def delete(self, key: str) -> None:
        """从 MinIO 删除文件。"""
        # ... 原有实现保持不变 ...
```

- [ ] **Step 6: 为 exists 方法添加装饰器**

```python
    @StorageMetrics.track_operation("exists")
    async def exists(self, key: str) -> bool:
        """检查 MinIO 对象是否存在。"""
        # ... 原有实现保持不变 ...
```

- [ ] **Step 7: 为 list_objects 方法添加装饰器**

```python
    @StorageMetrics.track_operation("list")
    async def list_objects(
        self,
        prefix: str = "",
        recursive: bool = True,
    ) -> List[str]:
        """列出对象。"""
        # ... 原有实现保持不变 ...
```

- [ ] **Step 8: 为 copy 方法添加装饰器**

```python
    @StorageMetrics.track_operation("copy")
    async def copy(
        self,
        source_key: str,
        dest_key: str,
    ) -> str:
        """复制对象。"""
        # ... 原有实现保持不变 ...
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/core/storage/minio.py
git commit -m "feat: integrate storage metrics into MinIO implementation

- Add StorageMetrics decorator to all storage operations
- Track upload, download, delete, exists, list, copy operations
- Maintain original implementation logic unchanged

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 10: 集成存储层指标到本地存储

**Files:**
- Modify: `backend/app/core/storage/local.py`

- [ ] **Step 1: 读取本地存储实现**

```bash
head -50 backend/app/core/storage/local.py
```

Expected: 看到导入部分和 LocalStorage 类定义

- [ ] **Step 2: 添加指标装饰器导入**

在 `backend/app/core/storage/local.py` 文件顶部导入部分添加：

```python
from app.core.metrics.storage_metrics import StorageMetrics
```

- [ ] **Step 3: 为 upload 方法添加装饰器**

```python
    @StorageMetrics.track_operation("upload")
    async def upload(
        self,
        key: str,
        content: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """上传文件到本地存储。"""
        # ... 原有实现保持不变 ...
```

- [ ] **Step 4: 为其他方法添加装饰器**

与 MinIO 实现类似，为 `download`, `delete`, `exists`, `list_objects`, `copy` 方法添加装饰器。

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/storage/local.py
git commit -m "feat: integrate storage metrics into local storage implementation

- Add StorageMetrics decorator to all storage operations
- Track upload, download, delete, exists, list, copy operations
- Maintain original implementation logic unchanged

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 11: 注册 Prometheus 中间件到 FastAPI

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: 读取 FastAPI 应用入口**

```bash
cat backend/app/main.py
```

Expected: 看到 FastAPI 应用初始化代码

- [ ] **Step 2: 添加指标导入**

在 `backend/app/main.py` 文件顶部导入部分添加：

```python
from app.core.metrics import setup_app_metrics
```

- [ ] **Step 3: 在应用启动时注册指标中间件**

找到 `app = FastAPI(...)` 后的位置，添加：

```python
# 注册 Prometheus 指标中间件
setup_app_metrics(app)
```

- [ ] **Step 4: 启动应用测试指标端点**

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &
```

然后在另一个终端测试：

```bash
curl http://localhost:8000/metrics
```

Expected: 返回 Prometheus 格式的指标数据

- [ ] **Step 5: 停止应用**

```bash
pkill -f "uvicorn app.main:app"
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: register Prometheus middleware in FastAPI app

- Import setup_app_metrics from core.metrics
- Register metrics collection on app startup
- Expose /metrics endpoint for Prometheus scraping

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 12: 创建指标单元测试

**Files:**
- Create: `backend/tests/test_metrics.py`

- [ ] **Step 1: 创建指标测试文件**

创建 `backend/tests/test_metrics.py`：

```python
"""指标采集单元测试。"""
import pytest
from unittest.mock import AsyncMock, patch
from prometheus_client import REGISTRY

from app.core.metrics.storage_metrics import StorageMetrics
from app.core.metrics.business_metrics import BusinessMetrics


class TestStorageMetrics:
    """存储层指标测试。"""

    @pytest.mark.asyncio
    async def test_track_operation_success(self):
        """测试成功操作指标采集。"""
        # 清空注册表
        for collector in list(REGISTRY._names_to_collectors.values()):
            if hasattr(collector, '_metrics'):
                collector._metrics.clear()

        @StorageMetrics.track_operation("upload")
        async def mock_upload(key: str, content: bytes):
            return "/uploads/test.txt"

        # 执行操作
        result = await mock_upload("test.txt", b"hello world")

        # 验证返回值
        assert result == "/uploads/test.txt"

        # 验证指标（这里只是验证不会抛出异常）
        # 实际指标值检查需要更复杂的设置

    @pytest.mark.asyncio
    async def test_track_operation_error(self):
        """测试错误操作指标采集。"""
        # 清空注册表
        for collector in list(REGISTRY._names_to_collectors.values()):
            if hasattr(collector, '_metrics'):
                collector._metrics.clear()

        @StorageMetrics.track_operation("download")
        async def mock_download(key: str):
            raise FileNotFoundError("文件不存在")

        # 执行操作，期望抛出异常
        with pytest.raises(FileNotFoundError):
            await mock_download("nonexistent.txt")


class TestBusinessMetrics:
    """业务层指标测试。"""

    def test_record_parse(self):
        """测试解析任务指标记录。"""
        # 清空注册表
        for collector in list(REGISTRY._names_to_collectors.values()):
            if hasattr(collector, '_metrics'):
                collector._metrics.clear()

        # 记录指标
        BusinessMetrics.record_parse(
            status="success",
            duration=5.0,
            chunks_count=10
        )

        # 验证不会抛出异常

    def test_record_workflow(self):
        """测试工作流指标记录。"""
        # 清空注册表
        for collector in list(REGISTRY._names_to_collectors.values()):
            if hasattr(collector, '_metrics'):
                collector._metrics.clear()

        # 记录指标
        BusinessMetrics.record_workflow(
            workflow_id="wf-001",
            status="success",
            duration=30.0
        )

        # 验证不会抛出异常

    def test_record_agent_conversation(self):
        """测试 Agent 对话指标记录。"""
        # 清空注册表
        for collector in list(REGISTRY._names_to_collectors.values()):
            if hasattr(collector, '_metrics'):
                collector._metrics.clear()

        # 记录指标
        BusinessMetrics.record_agent_conversation(agent_id="agent-001")
        BusinessMetrics.record_agent_message(message_type="user")
        BusinessMetrics.record_agent_message(message_type="assistant")

        # 验证不会抛出异常
```

- [ ] **Step 2: 运行指标测试**

```bash
cd backend
uv run pytest tests/test_metrics.py -v
```

Expected: 所有测试通过

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_metrics.py
git commit -m "test: add metrics collection unit tests

- Test StorageMetrics decorator with success and error cases
- Test BusinessMetrics record methods for parse, workflow, agent
- Verify metrics collection does not throw exceptions

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 13: 创建 Prometheus 配置文件

**Files:**
- Create: `backend/deploy/prometheus/prometheus.yml`

- [ ] **Step 1: 创建 Prometheus 配置目录**

```bash
mkdir -p backend/deploy/prometheus/alerts
mkdir -p backend/deploy/prometheus/grafana/dashboards
mkdir -p backend/deploy/prometheus/grafana/datasources
```

- [ ] **Step 2: 创建 Prometheus 配置文件**

创建 `backend/deploy/prometheus/prometheus.yml`：

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
  - static_configs:
    - targets:
      - alertmanager:9093

rule_files:
  - /etc/prometheus/alerts/*.yml

scrape_configs:
  - job_name: 'easyrag-api'
    static_configs:
      - targets: ['host.docker.internal:8000']
    metrics_path: '/metrics'
```

- [ ] **Step 3: Commit**

```bash
git add backend/deploy/prometheus/
git commit -m "feat: add Prometheus configuration

- Configure scrape interval: 15s
- Add easyrag-api job targeting host.docker.internal:8000
- Configure alertmanager integration
- Configure alert rule files

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 14: 创建 AlertManager 配置文件

**Files:**
- Create: `backend/deploy/prometheus/alertmanager.yml`

- [ ] **Step 1: 创建 AlertManager 配置文件**

创建 `backend/deploy/prometheus/alertmanager.yml`：

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'
  routes:
  - match:
      severity: critical
    receiver: 'critical'
  - match:
      severity: warning
    receiver: 'warning'

receivers:
- name: 'default'
  webhook_configs:
  - url: 'http://localhost:5001/webhook'

- name: 'critical'
  webhook_configs:
  - url: 'http://localhost:5001/webhook/critical'

- name: 'warning'
  webhook_configs:
  - url: 'http://localhost:5001/webhook/warning'
```

- [ ] **Step 2: Commit**

```bash
git add backend/deploy/prometheus/alertmanager.yml
git commit -m "feat: add AlertManager configuration

- Configure alert grouping by name and severity
- Set alert routing to different receivers based on severity
- Configure webhook receivers for default, critical, and warning

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 15: 创建应用层告警规则

**Files:**
- Create: `backend/deploy/prometheus/alerts/app_alerts.yml`

- [ ] **Step 1: 创建应用层告警规则文件**

创建 `backend/deploy/prometheus/alerts/app_alerts.yml`：

```yaml
groups:
- name: app_alerts
  rules:
  # 高错误率
  - alert: HighErrorRate
    expr: |
      rate(http_requests_total{status=~"5.."}[5m])
      /
      rate(http_requests_total[5m])
      > 0.03
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "高错误率告警"
      description: "API 错误率超过 3%（当前: {{ $value | humanizePercentage }}）"

  # 高延迟
  - alert: HighLatency
    expr: |
      histogram_quantile(0.95, http_request_duration_seconds_bucket)
      > 1.0
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "API 响应延迟过高"
      description: "P95 延迟超过 1 秒（当前: {{ $value | humanizeDuration }}）"

  # 服务不可用
  - alert: ServiceDown
    expr: up{job="easyrag-api"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "服务不可用"
      description: "EasyRAG API 服务已停止响应"
```

- [ ] **Step 2: Commit**

```bash
git add backend/deploy/prometheus/alerts/app_alerts.yml
git commit -m "feat: add application-level alert rules

- HighErrorRate: API error rate > 3% for 2m
- HighLatency: P95 latency > 1s for 5m
- ServiceDown: Service unavailable for 1m

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 16: 创建存储层告警规则

**Files:**
- Create: `backend/deploy/prometheus/alerts/storage_alerts.yml`

- [ ] **Step 1: 创建存储层告警规则文件**

创建 `backend/deploy/prometheus/alerts/storage_alerts.yml`：

```yaml
groups:
- name: storage_alerts
  rules:
  # 存储错误率高
  - alert: HighStorageErrorRate
    expr: |
      rate(easyrag_storage_operations_total{status="error"}[5m])
      /
      rate(easyrag_storage_operations_total[5m])
      > 0.05
    for: 3m
    labels:
      severity: critical
    annotations:
      summary: "存储错误率过高"
      description: "存储操作错误率超过 5%（当前: {{ $value | humanizePercentage }}）"

  # 上传延迟过高
  - alert: HighUploadLatency
    expr: |
      histogram_quantile(0.95, easyrag_storage_operation_duration_seconds_bucket{operation="upload"})
      > 5.0
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "上传延迟过高"
      description: "上传操作 P95 延迟超过 5 秒（当前: {{ $value | humanizeDuration }}）"

  # MinIO 连接失败
  - alert: MinioConnectionFailed
    expr: easyrag_storage_operations_total{operation="upload",status="error"} > 0
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "MinIO 连接失败"
      description: "连续 2 分钟无法连接到 MinIO"
```

注意：指标名称前缀使用 `easyrag_`（来自 `settings.metrics_namespace`）

- [ ] **Step 2: Commit**

```bash
git add backend/deploy/prometheus/alerts/storage_alerts.yml
git commit -m "feat: add storage-level alert rules

- HighStorageErrorRate: Storage error rate > 5% for 3m
- HighUploadLatency: Upload P95 latency > 5s for 5m
- MinioConnectionFailed: MinIO connection failure for 2m

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 17: 创建业务层告警规则

**Files:**
- Create: `backend/deploy/prometheus/alerts/business_alerts.yml`

- [ ] **Step 1: 创建业务层告警规则文件**

创建 `backend/deploy/prometheus/alerts/business_alerts.yml`：

```yaml
groups:
- name: business_alerts
  rules:
  # 文档解析失败率高
  - alert: HighParseFailureRate
    expr: |
      rate(easyrag_parse_documents_total{status="failed"}[10m])
      /
      rate(easyrag_parse_documents_total[10m])
      > 0.10
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "文档解析失败率过高"
      description: "解析失败率超过 10%（当前: {{ $value | humanizePercentage }}）"

  # 工作流执行失败
  - alert: WorkflowExecutionFailed
    expr: rate(easyrag_workflow_executions_total{status="failed"}[5m]) > 0
    for: 3m
    labels:
      severity: warning
    annotations:
      summary: "工作流执行失败"
      description: "工作流 {{ $labels.workflow_id }} 执行失败"

  # 检索测试通过率低
  - alert: LowRetrievalTestPassRate
    expr: |
      rate(easyrag_retrieval_tests_total{status="success"}[10m])
      /
      rate(easyrag_retrieval_tests_total[10m])
      < 0.80
    for: 10m
    labels:
      severity: info
    annotations:
      summary: "检索测试通过率偏低"
      description: "检索测试通过率低于 80%（当前: {{ $value | humanizePercentage }}）"
```

- [ ] **Step 2: Commit**

```bash
git add backend/deploy/prometheus/alerts/business_alerts.yml
git commit -m "feat: add business-level alert rules

- HighParseFailureRate: Parse failure rate > 10% for 5m
- WorkflowExecutionFailed: Workflow execution failure for 3m
- LowRetrievalTestPassRate: Retrieval test pass rate < 80% for 10m

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 18: 创建 Grafana 数据源配置

**Files:**
- Create: `backend/deploy/prometheus/grafana/datasources/prometheus.yml`
- Create: `backend/deploy/prometheus/grafana/datasources/datasources.yml`

- [ ] **Step 1: 创建数据源配置文件**

创建 `backend/deploy/prometheus/grafana/datasources/prometheus.yml`：

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

- [ ] **Step 2: 创建数据源自动加载配置**

创建 `backend/deploy/prometheus/grafana/datasources/datasources.yml`：

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

注意：通常只需要一个 `prometheus.yml` 文件即可，`datasources.yml` 是可选的。

- [ ] **Step 3: Commit**

```bash
git add backend/deploy/prometheus/grafana/datasources/
git commit -m "feat: add Grafana Prometheus datasource configuration

- Configure Prometheus datasource
- Set datasource as default
- Configure proxy access mode

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 19: 创建 Grafana 仪表板自动加载配置

**Files:**
- Create: `backend/deploy/prometheus/grafana/dashboard.yml`

- [ ] **Step 1: 创建仪表板自动加载配置**

创建 `backend/deploy/prometheus/grafana/dashboard.yml`：

```yaml
apiVersion: 1

providers:
  - name: 'EasyRAG Dashboards'
    orgId: 1
    folder: ''
    folderUid: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
```

- [ ] **Step 2: Commit**

```bash
git add backend/deploy/prometheus/grafana/dashboard.yml
git commit -m "feat: add Grafana dashboard auto-provisioning configuration

- Configure dashboard provider
- Set dashboard update interval: 30s
- Enable UI updates

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 20: 创建应用概览仪表板

**Files:**
- Create: `backend/deploy/prometheus/grafana/dashboards/app-overview.json`

- [ ] **Step 1: 创建应用概览仪表板 JSON**

由于 Grafana 仪表板 JSON 文件较长，这里创建一个简化版本。实际项目中可以使用 Grafana UI 导出完整配置。

创建 `backend/deploy/prometheus/grafana/dashboards/app-overview.json`：

```json
{
  "annotations": {
    "list": []
  },
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "liveNow": false,
  "panels": [
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              }
            ]
          },
          "unit": "reqps"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 4,
        "w": 6,
        "x": 0,
        "y": 0
      },
      "id": 1,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "values": false,
          "calcs": [
            "lastNotNull"
          ],
          "fields": ""
        },
        "textMode": "auto"
      },
      "pluginVersion": "10.0.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "prometheus"
          },
          "expr": "rate(http_requests_total[5m])",
          "refId": "A"
        }
      ],
      "title": "请求速率 (QPS)",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "yellow",
                "value": 0.01
              },
              {
                "color": "red",
                "value": 0.03
              }
            ]
          },
          "unit": "percentunit"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 4,
        "w": 6,
        "x": 6,
        "y": 0
      },
      "id": 2,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "values": false,
          "calcs": [
            "lastNotNull"
          ],
          "fields": ""
        },
        "textMode": "auto"
      },
      "pluginVersion": "10.0.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "prometheus"
          },
          "expr": "rate(http_requests_total{status=~\"5..\"}[5m]) / rate(http_requests_total[5m])",
          "refId": "A"
        }
      ],
      "title": "错误率",
      "type": "stat"
    }
  ],
  "refresh": "5s",
  "schemaVersion": 38,
  "style": "dark",
  "tags": [],
  "templating": {
    "list": []
  },
  "time": {
    "from": "now-1h",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "",
  "title": "EasyRAG 应用概览",
  "uid": "app-overview",
  "version": 1,
  "weekStart": ""
}
```

注意：这是一个简化的仪表板配置。实际项目中建议使用 Grafana UI 创建完整仪表板后导出 JSON。

- [ ] **Step 2: Commit**

```bash
git add backend/deploy/prometheus/grafana/dashboards/app-overview.json
git commit -m "feat: add Grafana application overview dashboard

- Create basic app overview dashboard JSON
- Include QPS and error rate panels
- Configure refresh interval: 5s

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 21: 创建存储详情仪表板

**Files:**
- Create: `backend/deploy/prometheus/grafana/dashboards/storage-details.json`

- [ ] **Step 1: 创建存储详情仪表板 JSON**

创建 `backend/deploy/prometheus/grafana/dashboards/storage-details.json`：

```json
{
  "annotations": {
    "list": []
  },
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "liveNow": false,
  "panels": [
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "yellow",
                "value": 0.95
              },
              {
                "color": "red",
                "value": 0.99
              }
            ]
          },
          "unit": "percentunit"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 4,
        "w": 6,
        "x": 0,
        "y": 0
      },
      "id": 1,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "values": false,
          "calcs": [
            "lastNotNull"
          ],
          "fields": ""
        },
        "textMode": "auto"
      },
      "pluginVersion": "10.0.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "prometheus"
          },
          "expr": "rate(easyrag_storage_operations_total{status=\"success\"}[5m]) / rate(easyrag_storage_operations_total[5m])",
          "refId": "A"
        }
      ],
      "title": "操作成功率",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              }
            ]
          },
          "unit": "Bps"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 4,
        "w": 6,
        "x": 6,
        "y": 0
      },
      "id": 2,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "values": false,
          "calcs": [
            "lastNotNull"
          ],
          "fields": ""
        },
        "textMode": "auto"
      },
      "pluginVersion": "10.0.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "prometheus"
          },
          "expr": "rate(easyrag_storage_bytes_transferred_total[5m])",
          "refId": "A"
        }
      ],
      "title": "吞吐量 (B/s)",
      "type": "stat"
    }
  ],
  "refresh": "5s",
  "schemaVersion": 38,
  "style": "dark",
  "tags": [],
  "templating": {
    "list": []
  },
  "time": {
    "from": "now-1h",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "",
  "title": "EasyRAG 存储详情",
  "uid": "storage-details",
  "version": 1,
  "weekStart": ""
}
```

- [ ] **Step 2: Commit**

```bash
git add backend/deploy/prometheus/grafana/dashboards/storage-details.json
git commit -m "feat: add Grafana storage details dashboard

- Create storage details dashboard JSON
- Include operation success rate and throughput panels
- Configure refresh interval: 5s

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 22: 创建业务指标仪表板

**Files:**
- Create: `backend/deploy/prometheus/grafana/dashboards/business-metrics.json`

- [ ] **Step 1: 创建业务指标仪表板 JSON**

创建 `backend/deploy/prometheus/grafana/dashboards/business-metrics.json`：

```json
{
  "annotations": {
    "list": []
  },
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "liveNow": false,
  "panels": [
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "yellow",
                "value": 0.90
              },
              {
                "color": "red",
                "value": 0.95
              }
            ]
          },
          "unit": "percentunit"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 4,
        "w": 6,
        "x": 0,
        "y": 0
      },
      "id": 1,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "values": false,
          "calcs": [
            "lastNotNull"
          ],
          "fields": ""
        },
        "textMode": "auto"
      },
      "pluginVersion": "10.0.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "prometheus"
          },
          "expr": "rate(easyrag_parse_documents_total{status=\"success\"}[5m]) / rate(easyrag_parse_documents_total[5m])",
          "refId": "A"
        }
      ],
      "title": "解析成功率",
      "type": "stat"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              }
            ]
          },
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 4,
        "w": 6,
        "x": 6,
        "y": 0
      },
      "id": 2,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "values": false,
          "calcs": [
            "lastNotNull"
          ],
          "fields": ""
        },
        "textMode": "auto"
      },
      "pluginVersion": "10.0.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "prometheus"
          },
          "expr": "rate(easyrag_parse_documents_total[5m]) * 60",
          "refId": "A"
        }
      ],
      "title": "解析吞吐量 (docs/min)",
      "type": "stat"
    }
  ],
  "refresh": "5s",
  "schemaVersion": 38,
  "style": "dark",
  "tags": [],
  "templating": {
    "list": []
  },
  "time": {
    "from": "now-1h",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "",
  "title": "EasyRAG 业务指标",
  "uid": "business-metrics",
  "version": 1,
  "weekStart": ""
}
```

- [ ] **Step 2: Commit**

```bash
git add backend/deploy/prometheus/grafana/dashboards/business-metrics.json
git commit -m "feat: add Grafana business metrics dashboard

- Create business metrics dashboard JSON
- Include parse success rate and throughput panels
- Configure refresh interval: 5s

Co-Authored-By: lilin <565387073@qq.com>"
```

---

### Task 23: 创建 Docker Compose 监控栈

**Files:**
- Create: `backend/deploy/docker-compose.monitoring.yml`

- [ ] **Step 1: 创建 Docker Compose 监控栈配置**

创建 `backend/deploy/docker-compose.monitoring.yml`：

```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: easyrag-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./prometheus/alerts:/etc/prometheus/alerts
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:latest
    container_name: easyrag-alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./prometheus/alertmanager.yml:/etc/alertmanager/alertmanager.yml
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: easyrag-grafana
    ports:
      - "3000:3000"
    volumes:
      - ./prometheus/grafana/datasources:/etc/grafana/provisioning/datasources
      - ./prometheus/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./prometheus/grafana/dashboard.yml:/etc/grafana/provisioning/dashboards/dashboard.yml
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin123
    restart: unless-stopped

networks:
  default:
    name: easyrag_network
    external: false
```

- [ ] **Step 2: Commit**

```bash
git add backend/deploy/docker-compose.monitoring.yml
git commit -m "feat: add Docker Compose monitoring stack

- Configure Prometheus service on port 9090
- Configure AlertManager service on port 9093
- Configure Grafana service on port 3000
- Mount configuration volumes for all services

Co-Authored-By: lilin <565387073@qq.com>"
```

---

## 测试与验证

### Task 24: 验证 MinIO 存储切换

**Files:**
- Test: `backend/tests/test_storage.py`

- [ ] **Step 1: 配置 MinIO 存储**

修改 `backend/.env` 或设置环境变量：

```bash
STORAGE_TYPE=minio
MINIO_ENDPOINT=192.168.137.13:9000
MINIO_ACCESS_KEY=easyrag
MINIO_SECRET_KEY=easyrag2026
MINIO_BUCKET=easyrag
MINIO_SECURE=false
```

- [ ] **Step 2: 测试 MinIO 连接**

```bash
cd backend
uv run python -c "
from app.core.storage import get_storage
import asyncio

storage = get_storage()
print(f'Storage type: {type(storage).__name__}')

async def test():
    # 上传测试
    result = await storage.upload('metrics-test/test.txt', b'test content')
    print(f'Upload: {result}')

    # 下载测试
    data = await storage.download('metrics-test/test.txt')
    print(f'Download: {data}')

    # 删除测试
    await storage.delete('metrics-test/test.txt')
    print('Delete: success')

asyncio.run(test())
"
```

Expected: 所有操作成功

- [ ] **Step 3: 运行存储测试**

```bash
cd backend
uv run pytest tests/test_storage.py -v
```

Expected: 所有测试通过

---

### Task 25: 验证 Prometheus 指标采集

**Files:**
- Test: `backend/tests/test_metrics.py`

- [ ] **Step 1: 启动应用**

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &
```

- [ ] **Step 2: 测试 /metrics 端点**

```bash
curl http://localhost:8000/metrics | grep easyrag
```

Expected: 返回包含 `easyrag_` 前缀的指标

- [ ] **Step 3: 触发存储操作生成指标**

```bash
# 上传文件
curl -X POST http://localhost:8000/api/v2/assets/upload \
  -F "file=@test.txt"

# 再次检查指标
curl http://localhost:8000/metrics | grep easyrag_storage
```

Expected: 看到存储操作指标

- [ ] **Step 4: 停止应用**

```bash
pkill -f "uvicorn app.main:app"
```

---

### Task 26: 启动监控栈验证

**Files:**
- None

- [ ] **Step 1: 启动 Docker Compose 监控栈**

```bash
cd backend/deploy
docker-compose -f docker-compose.monitoring.yml up -d
```

Expected: 三个容器（prometheus, alertmanager, grafana）启动成功

- [ ] **Step 2: 访问 Prometheus UI**

打开浏览器访问：http://localhost:9090

Expected: Prometheus UI 正常加载

- [ ] **Step 3: 访问 Grafana UI**

打开浏览器访问：http://localhost:3000

使用凭据登录：
- Username: admin
- Password: admin123

Expected: Grafana UI 正常加载，可以看到仪表板

- [ ] **Step 4: 停止监控栈**

```bash
cd backend/deploy
docker-compose -f docker-compose.monitoring.yml down
```

---

## 总结与提交

### Task 27: 最终验证和提交

**Files:**
- None

- [ ] **Step 1: 运行所有测试**

```bash
cd backend
uv run pytest tests/ -v
```

Expected: 所有测试通过

- [ ] **Step 2: 检查 git 状态**

```bash
git status
```

Expected: 所有修改已提交

- [ ] **Step 3: 推送到远程仓库**

```bash
git push origin feat/backend
```

Expected: 推送成功

---

## 实施注意事项

1. **TDD 原则**：每个任务都遵循"先写测试 → 实现 → 测试通过 → 提交"的流程

2. **频繁提交**：每个小步骤完成后立即提交，便于回滚和追踪

3. **指标命名约定**：使用 `easyrag_` 前缀（来自 `settings.metrics_namespace`），确保指标名称一致

4. **环境隔离**：监控栈使用独立的 Docker network（`easyrag_network`），避免与现有基础设施冲突

5. **配置验证**：所有配置项都有默认值，确保开发环境无需额外配置即可运行

6. **健康检查**：存储健康检查支持两种存储类型，确保错误信息详细

7. **仪表板简化**：Grafana 仪表板 JSON 为简化版本，实际使用中建议通过 Grafana UI 完善后导出

8. **告警通知**：AlertManager 配置使用 webhook，实际项目中需要配置邮件/Slack/钉钉等通知渠道

---

**计划创建完成！** 🎉