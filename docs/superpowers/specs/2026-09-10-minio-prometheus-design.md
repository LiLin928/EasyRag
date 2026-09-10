# EasyRAG MinIO 存储集成与 Prometheus 监控设计方案

> 版本：v1.0
> 日期：2026-09-10
> 作者：Claude Code

---

## 1. 概述

### 1.1 目标

将 EasyRAG 后端的文件存储统一切换到 MinIO，并集成 Prometheus 监控系统，实现对应用、存储、业务的全维度可观测性。

### 1.2 背景

**存储现状**：
- 项目中存在两套存储系统：`app/providers/storage/`（旧版）和 `app/core/storage/`（新版）
- MinIO 实现已完成（`app/core/storage/minio.py`），但未启用
- 配置已就绪，虚拟机 MinIO 服务运行在 192.168.137.13:9000

**监控现状**：
- 未集成任何监控方案
- 缺乏可观测性，难以发现性能瓶颈和故障

### 1.3 范围

**存储切换**：
- 统一使用 `app/core/storage` 工厂
- 启用 MinIO 作为主要存储后端
- 旧数据保留本地，新数据使用 MinIO

**Prometheus 集成**：
- 应用层：HTTP 请求、延迟、错误率
- 存储层：MinIO 操作统计
- 业务层：文档解析、工作流、Agent 对话
- Grafana 仪表板可视化
- AlertManager 告警规则

---

## 2. 存储切换设计

### 2.1 实施策略

**原则**：新数据直接使用 MinIO，旧数据保留本地，无需数据迁移。

**影响范围**：
- `app/providers/storage/factory.py` - 修改为调用 `app/core/storage` 工厂
- 使用此工厂的文件：
  - `app/api/v2/assets.py` ✅
  - `app/worker/tasks/parse_tasks.py` ✅
  - `app/services/document_service_celery.py` ✅

### 2.2 代码修改

#### 修改工厂配置

**文件**：`app/providers/storage/factory.py`

```python
# 当前代码（旧工厂）
def get_storage() -> ObjectStorage:
    if settings.storage_type == "minio":
        # MinIO 实现将在 Phase3 添加
        from app.providers.storage.local_fs import LocalFSStorage
        return LocalFSStorage(settings.storage_local_dir)
    from app.providers.storage.local_fs import LocalFSStorage
    return LocalFSStorage(settings.storage_local_dir)

# 修改为：直接调用新工厂
def get_storage():
    """返回配置的对象存储实例（local | minio）。"""
    from app.core.storage import get_storage as core_get_storage
    return core_get_storage()
```

### 2.3 配置验证

**新增文件**：`app/core/storage/health.py`

**功能**：
- MinIO 连接检查
- Bucket 权限验证
- 存储健康状态返回（供 `/health` 端点使用）

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
            # 测试 MinIO 连接
            # 尝试列出一个不存在的对象
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

---

## 3. Prometheus 集成设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                     │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  API Layer   │  │ Service Layer│  │  Storage     │     │
│  │              │  │              │  │  Layer       │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                 │              │
│  ┌──────▼─────────────────▼─────────────────▼──────┐       │
│  │         Metrics Collection Layer                │       │
│  │  ┌───────────────┐  ┌───────────────┐          │       │
│  │  │ AppMetrics    │  │ StorageMetrics│          │       │
│  │  │ (Instrumentator)│  │ (Custom)     │          │       │
│  │  └───────────────┘  └───────────────┘          │       │
│  │  ┌───────────────┐                             │       │
│  │  │ BusinessMetrics│                            │       │
│  │  │ (Custom)      │                             │       │
│  │  └───────────────┘                             │       │
│  └─────────────────────────────────────────────────┘       │
│                          │                                  │
│                          ▼                                  │
│               /metrics endpoint                             │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │   Prometheus    │
                  │   (scrape)      │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │    Grafana      │
                  │  (dashboards)   │
                  └─────────────────┘
```

### 3.2 指标分类

#### 应用层指标

**实现方式**：`prometheus-fastapi-instrumentator`

**采集指标**：
- `http_requests_total` - HTTP 请求总数（按 method、endpoint、status）
- `http_request_duration_seconds` - 请求延迟分布
- `http_requests_in_progress` - 正在处理的请求数
- `http_response_size_bytes` - 响应大小
- `http_request_size_bytes` - 请求大小

**集成位置**：`app/main.py`（应用启动时）

#### 存储层指标

**实现方式**：自定义 `StorageMetrics` 类（基于 `prometheus_client`）

**采集指标**：
```python
# Counter - 操作次数
storage_operations_total{operation, status}
  - operation: upload, download, delete, exists, copy, list
  - status: success, error

# Histogram - 操作延迟
storage_operation_duration_seconds{operation}
  - buckets: [0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]

# Counter - 传输字节数
storage_bytes_transferred_total{operation, direction}
  - operation: upload, download
  - direction: in, out

# Gauge - 当前状态
storage_active_operations{operation}
```

**集成位置**：
- `app/core/storage/minio.py` - MinIO 实现装饰器
- `app/core/storage/local.py` - 本地实现装饰器
- 通过装饰器模式，不侵入业务逻辑

#### 业务层指标

**实现方式**：自定义 `BusinessMetrics` 类

**采集指标**：
```python
# 文档解析
parse_documents_total{status} - 解析任务总数
parse_document_duration_seconds - 解析耗时
parse_chunks_created_total - 生成的 chunk 总数

# 工作流执行
workflow_executions_total{workflow_id, status} - 工作流执行数
workflow_execution_duration_seconds{workflow_id} - 执行耗时
workflow_steps_total{step_type, status} - 步骤执行数

# Agent 对话
agent_conversations_total{agent_id} - 对话总数
agent_messages_total{type} - 消息总数（user/assistant）
agent_tool_calls_total{tool_name, status} - 工具调用次数

# 检索测试
retrieval_tests_total{status} - 测试总数
retrieval_test_latency_seconds - 测试延迟
```

**集成位置**：
- `app/worker/tasks/parse_tasks.py` - 解析任务
- `app/worker/tasks/workflow_tasks.py` - 工作流任务
- `app/worker/tasks/agent_tasks.py` - Agent 任务
- `app/services/retrieval_test_service.py` - 检索测试

### 3.3 代码结构

#### 目录结构

```
backend/
├── app/
│   ├── core/
│   │   ├── metrics/                    # 新增：指标采集模块
│   │   │   ├── __init__.py            # 导出所有指标类
│   │   │   ├── app_metrics.py         # 应用层指标
│   │   │   ├── storage_metrics.py     # 存储层指标
│   │   │   └── business_metrics.py    # 业务层指标
│   │   │
│   │   └── storage/                    # 已存在，稍作修改
│   │       ├── __init__.py            # 工厂（已支持 MinIO）
│   │       ├── interface.py           # 接口定义（已存在）
│   │       ├── minio.py               # MinIO 实现 + 指标装饰器
│   │       ├── local.py               # 本地实现 + 指标装饰器
│   │       └── health.py              # 新增：健康检查
│   │
│   ├── providers/
│   │   └── storage/
│   │       └── factory.py              # 修改：调用 core.storage
│   │
│   └── main.py                         # 修改：注册 Prometheus 中间件
│
├── deploy/
│   ├── prometheus/                     # 新增：监控配置
│   │   ├── prometheus.yml             # Prometheus 配置
│   │   ├── alertmanager.yml           # AlertManager 配置
│   │   ├── alerts/                    # 告警规则
│   │   │   ├── app_alerts.yml
│   │   │   ├── storage_alerts.yml
│   │   │   └── business_alerts.yml
│   │   └── grafana/                   # Grafana 配置
│   │       ├── dashboards/            # 仪表板 JSON
│   │       │   ├── app-overview.json
│   │       │   ├── storage-details.json
│   │       │   └── business-metrics.json
│   │       ├── datasources/           # 数据源配置
│   │       │   └── prometheus.yml
│   │       └── dashboard.yml          # 仪表板自动加载配置
│   │
│   └── docker-compose.monitoring.yml  # 新增：监控栈编排
│
├── tests/
│   └── test_metrics.py                # 新增：指标测试
│
└── pyproject.toml                      # 修改：添加依赖
```

#### 依赖管理

**新增依赖** (`pyproject.toml`)：
```toml
dependencies = [
  # ... 现有依赖 ...

  # Prometheus 监控
  "prometheus-client>=0.19.0",                    # Prometheus Python 客户端
  "prometheus-fastapi-instrumentator>=7.0.0",     # FastAPI 集成
]

[project.optional-dependencies]
monitoring = [
  "prometheus-client>=0.19.0",
  "prometheus-fastapi-instrumentator>=7.0.0",
]
```

#### 配置管理

**环境变量** (`.env` 新增)：
```bash
# Prometheus 配置
PROMETHEUS_ENABLED=true                    # 是否启用 Prometheus
PROMETHEUS_PORT=9090                       # Prometheus 端口
PROMETHEUS_SCRAPE_INTERVAL=15s             # 采集间隔

# Grafana 配置
GRAFANA_ENABLED=true                       # 是否启用 Grafana
GRAFANA_PORT=3000                          # Grafana 端口

# AlertManager 配置
ALERTMANAGER_ENABLED=true                  # 是否启用告警
ALERTMANAGER_PORT=9093                     # AlertManager 端口
```

**配置类扩展** (`app/config.py`)：
```python
class Settings(BaseSettings):
    # ... 现有配置 ...

    # Prometheus 监控
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    prometheus_scrape_interval: int = 15

    # 指标标签
    metrics_namespace: str = "easyrag"
    metrics_environment: str = "development"
```

---

## 4. Grafana 仪表板设计

### 4.1 仪表板 1：应用概览

**用途**：全局视图，快速了解系统状态

**面板配置**：

**Row 1: 核心指标**
- 面板 1: 请求速率
  - 可视化: Stat
  - 指标: `rate(http_requests_total[5m])`
  - 显示: 当前 QPS

- 面板 2: 错误率
  - 可视化: Stat (阈值着色)
  - 指标: `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])`
  - 阈值: <1% 绿色, 1-3% 黄色, >3% 红色

- 面板 3: 平均延迟 (P50/P95/P99)
  - 可视化: Stat
  - 指标: `histogram_quantile(0.50, http_request_duration_seconds_bucket)`
  - 显示: P50、P95、P99 三个数值

- 面板 4: 活跃连接数
  - 可视化: Gauge
  - 指标: `http_requests_in_progress`
  - 阈值: 0-50 绿色, 50-100 黄色, >100 红色

**Row 2: 请求分布**
- 面板 5: 请求趋势
  - 可视化: Time series
  - 指标: `rate(http_requests_total[5m]) by (endpoint)`
  - 分组: 按 endpoint 分色

- 面板 6: 响应状态码分布
  - 可视化: Pie chart
  - 指标: `http_requests_total by (status)`
  - 显示: 2xx/4xx/5xx 比例

**Row 3: 端点详情**
- 面板 7: Top 10 慢端点
  - 可视化: Bar gauge
  - 指标: `topk(10, histogram_quantile(0.95, http_request_duration_seconds_bucket) by (endpoint))`
  - 显示: P95 延迟最高的 10 个端点

**变量**：
- `$interval` - 时间间隔选择器（1m, 5m, 15m, 1h）
- `$endpoint` - 端点过滤器（默认 all）

### 4.2 仪表板 2：存储详情

**用途**：监控 MinIO 存储性能和健康状态

**面板配置**：

**Row 1: 存储概览**
- 面板 1: 操作成功率
  - 可视化: Stat
  - 指标: `rate(storage_operations_total{status="success"}[5m]) / rate(storage_operations_total[5m])`
  - 阈值: >99% 绿色, 95-99% 黄色, <95% 红色

- 面板 2: 吞吐量
  - 可视化: Stat
  - 指标: `rate(storage_bytes_transferred_total[5m])`
  - 单位: MB/s

- 面板 3: 平均延迟
  - 可视化: Stat
  - 指标: `histogram_quantile(0.50, storage_operation_duration_seconds_bucket)`
  - 显示: 各操作的 P50 延迟

- 面板 4: 活跃操作数
  - 可视化: Gauge
  - 指标: `storage_active_operations`

**Row 2: 操作详情**
- 面板 5: 操作次数趋势
  - 可视化: Time series
  - 指标: `rate(storage_operations_total[5m]) by (operation, status)`
  - 分组: 按 operation 和 status 分色

- 面板 6: 操作延迟分布
  - 可视化: Heatmap
  - 指标: `storage_operation_duration_seconds`
  - 配置: Y 轴延迟，X 轴时间

- 面板 7: 错误类型分布
  - 可视化: Pie chart
  - 指标: `storage_operations_total{status="error"} by (operation)`
  - 显示: 各操作错误比例

**Row 3: 传输统计**
- 面板 8: 数据传输趋势
  - 可视化: Time series (stacked)
  - 指标: `rate(storage_bytes_transferred_total[5m]) by (operation, direction)`
  - 显示: 上传/下载流量堆叠图

**变量**：
- `$operation` - 操作类型过滤器
- `$status` - 状态过滤器

### 4.3 仪表板 3：业务指标

**用途**：监控核心业务流程健康状态

**面板配置**：

**Row 1: 文档解析**
- 面板 1: 解析成功率
  - 可视化: Stat
  - 指标: `rate(parse_documents_total{status="success"}[5m]) / rate(parse_documents_total[5m])`
  - 阈值: >95% 绿色, 90-95% 黄色, <90% 红色

- 面板 2: 解析吞吐量
  - 可视化: Stat
  - 指标: `rate(parse_documents_total[5m])`
  - 单位: docs/min

- 面板 3: 平均解析时长
  - 可视化: Stat
  - 指标: `histogram_quantile(0.50, parse_document_duration_seconds)`
  - 单位: 秒

**Row 2: 工作流执行**
- 面板 4: 工作流执行数
  - 可视化: Time series
  - 指标: `rate(workflow_executions_total[5m]) by (workflow_id, status)`
  - 分组: 按 workflow_id 和 status 分色

- 面板 5: 工作流延迟分布
  - 可视化: Heatmap
  - 指标: `workflow_execution_duration_seconds`
  - 配置: Y 轴延迟，X 轴时间

**Row 3: Agent 对话**
- 面板 6: 对话趋势
  - 可视化: Time series
  - 指标: `rate(agent_conversations_total[5m])`
  - 显示: 对话数随时间变化

- 面板 7: 工具调用统计
  - 可视化: Bar chart
  - 指标: `topk(10, rate(agent_tool_calls_total[5m]) by (tool_name))`
  - 显示: 最常用的 10 个工具

**Row 4: 检索测试**
- 面板 8: 测试通过率
  - 可视化: Stat
  - 指标: `rate(retrieval_tests_total{status="success"}[5m]) / rate(retrieval_tests_total[5m])`
  - 阈值: >90% 绿色, 80-90% 黄色, <80% 红色

---

## 5. AlertManager 告警规则

### 5.1 配置文件结构

```
deploy/prometheus/
├── alertmanager.yml          # AlertManager 配置
├── alerts/
│   ├── app_alerts.yml       # 应用层告警
│   ├── storage_alerts.yml   # 存储层告警
│   └── business_alerts.yml  # 业务层告警
└── grafana/
    ├── dashboards/          # 仪表板 JSON
    └── datasources/         # 数据源配置
```

### 5.2 应用层告警

**文件**：`deploy/prometheus/alerts/app_alerts.yml`

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

### 5.3 存储层告警

**文件**：`deploy/prometheus/alerts/storage_alerts.yml`

```yaml
groups:
- name: storage_alerts
  rules:
  # 存储错误率高
  - alert: HighStorageErrorRate
    expr: |
      rate(storage_operations_total{status="error"}[5m])
      /
      rate(storage_operations_total[5m])
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
      histogram_quantile(0.95, storage_operation_duration_seconds_bucket{operation="upload"})
      > 5.0
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "上传延迟过高"
      description: "上传操作 P95 延迟超过 5 秒（当前: {{ $value | humanizeDuration }}）"

  # MinIO 连接失败
  - alert: MinioConnectionFailed
    expr: storage_operations_total{operation="upload",status="error"} > 0
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "MinIO 连接失败"
      description: "连续 2 分钟无法连接到 MinIO"
```

### 5.4 业务层告警

**文件**：`deploy/prometheus/alerts/business_alerts.yml`

```yaml
groups:
- name: business_alerts
  rules:
  # 文档解析失败率高
  - alert: HighParseFailureRate
    expr: |
      rate(parse_documents_total{status="failed"}[10m])
      /
      rate(parse_documents_total[10m])
      > 0.10
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "文档解析失败率过高"
      description: "解析失败率超过 10%（当前: {{ $value | humanizePercentage }}）"

  # 工作流执行失败
  - alert: WorkflowExecutionFailed
    expr: rate(workflow_executions_total{status="failed"}[5m]) > 0
    for: 3m
    labels:
      severity: warning
    annotations:
      summary: "工作流执行失败"
      description: "工作流 {{ $labels.workflow_id }} 执行失败"

  # 检索测试通过率低
  - alert: LowRetrievalTestPassRate
    expr: |
      rate(retrieval_tests_total{status="success"}[10m])
      /
      rate(retrieval_tests_total[10m])
      < 0.80
    for: 10m
    labels:
      severity: info
    annotations:
      summary: "检索测试通过率偏低"
      description: "检索测试通过率低于 80%（当前: {{ $value | humanizePercentage }}）"
```

### 5.5 AlertManager 配置

**文件**：`deploy/prometheus/alertmanager.yml`

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
  # 可配置邮件/Slack/钉钉等通知渠道

- name: 'warning'
  webhook_configs:
  - url: 'http://localhost:5001/webhook/warning'
```

---

## 6. Docker Compose 监控栈

### 6.1 配置文件

**文件**：`deploy/docker-compose.monitoring.yml`

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
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin123
    restart: unless-stopped

networks:
  default:
    external:
      name: easyrag_network
```

### 6.2 Prometheus 配置

**文件**：`deploy/prometheus/prometheus.yml`

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
      - targets: ['host.docker.internal:8000']  # FastAPI 应用
    metrics_path: '/metrics'
```

---

## 7. 核心代码实现示例

### 7.1 应用层指标

**文件**：`app/core/metrics/app_metrics.py`

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

### 7.2 存储层指标

**文件**：`app/core/metrics/storage_metrics.py`

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
            operation: 操作类型

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

### 7.3 存储实现集成

**文件**：`app/core/storage/minio.py`（修改部分）

```python
"""MinIO 对象存储实现。"""
# ... 现有导入 ...
from app.core.metrics.storage_metrics import StorageMetrics


class MinioStorage:
    """MinIO 对象存储实现。"""

    # ... 现有代码 ...

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

    @StorageMetrics.track_operation("download")
    async def download(self, key: str) -> bytes:
        """从 MinIO 下载文件。"""
        # ... 原有实现保持不变 ...

    @StorageMetrics.track_operation("delete")
    async def delete(self, key: str) -> None:
        """从 MinIO 删除文件。"""
        # ... 原有实现保持不变 ...

    # ... 其他方法同理 ...
```

### 7.4 业务层指标

**文件**：`app/core/metrics/business_metrics.py`

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

# 工作流指标
WORKFLOW_EXECUTIONS_TOTAL = Counter(
    f"{settings.metrics_namespace}_workflow_executions_total",
    "Total workflow executions",
    ["workflow_id", "status"]
)

# Agent 指标
AGENT_CONVERSATIONS_TOTAL = Counter(
    f"{settings.metrics_namespace}_agent_conversations_total",
    "Total agent conversations",
    ["agent_id"]
)


class BusinessMetrics:
    """业务指标记录工具类。"""

    @staticmethod
    def record_parse(status: str, duration: float):
        """记录解析任务。

        Args:
            status: 解析状态
            duration: 解析耗时（秒）
        """
        PARSE_DOCUMENTS_TOTAL.labels(status=status).inc()
        PARSE_DOCUMENT_DURATION.observe(duration)

    @staticmethod
    def record_workflow(workflow_id: str, status: str):
        """记录工作流执行。

        Args:
            workflow_id: 工作流 ID
            status: 执行状态
        """
        WORKFLOW_EXECUTIONS_TOTAL.labels(
            workflow_id=workflow_id,
            status=status
        ).inc()

    @staticmethod
    def record_agent_conversation(agent_id: str):
        """记录 Agent 对话。

        Args:
            agent_id: Agent ID
        """
        AGENT_CONVERSATIONS_TOTAL.labels(agent_id=agent_id).inc()
```

---

## 8. 测试计划

### 8.1 单元测试

**文件**：`tests/test_metrics.py`

**测试内容**：
- 存储指标装饰器正确采集数据
- 业务指标记录方法正常工作
- 指标标签正确设置

### 8.2 集成测试

**测试内容**：
- MinIO 连接成功
- Prometheus `/metrics` 端点返回正确数据
- Grafana 仪表板正常加载

### 8.3 性能测试

**测试内容**：
- 指标采集对存储操作延迟的影响（应 < 5%）
- 高并发下指标采集的准确性

---

## 9. 实施计划

### 9.1 工作量估算

| 任务 | 工作量 | 说明 |
|------|--------|------|
| 存储切换 | 0.5 天 | 修改工厂配置，添加健康检查 |
| Prometheus 集成 | 1.5 天 | 三层指标采集 + 代码集成 |
| Grafana 仪表板 | 0.5 天 | 创建 3 个仪表板 JSON |
| 告警配置 | 0.5 天 | 编写告警规则 + AlertManager |
| 测试 | 0.5 天 | 单元测试 + 集成测试 |
| **总计** | **3.5 天** | - |

### 9.2 实施步骤

1. **存储切换**（第 1 天上午）
   - 修改 `app/providers/storage/factory.py`
   - 添加 `app/core/storage/health.py`
   - 测试 MinIO 连接

2. **Prometheus 集成**（第 1 天下午 - 第 2 天）
   - 创建 `app/core/metrics/` 模块
   - 实现三层指标采集
   - 集成到存储和业务代码
   - 添加配置管理

3. **Grafana 仪表板**（第 3 天上午）
   - 创建 3 个仪表板 JSON
   - 配置数据源
   - 测试仪表板加载

4. **告警配置**（第 3 天下午）
   - 编写告警规则
   - 配置 AlertManager
   - 测试告警触发

5. **测试**（第 4 天上午）
   - 单元测试
   - 集成测试
   - 性能测试

---

## 10. 风险与应对

### 10.1 存储切换风险

**风险**：MinIO 连接失败导致服务不可用

**应对**：
- 添加配置验证和健康检查
- 提供降级策略（回退到本地存储）
- 充分测试 MinIO 连接

### 10.2 性能风险

**风险**：指标采集影响存储操作性能

**应对**：
- 使用装饰器模式，最小化代码侵入
- 异步采集，不阻塞主流程
- 性能测试验证影响 < 5%

### 10.3 监控资源风险

**风险**：Prometheus 存储占用大量磁盘空间

**应对**：
- 配置合理的保留期（默认 15 天）
- 使用压缩减少存储占用
- 监控 Prometheus 资源使用

---

## 11. 附录

### 11.1 参考资料

- Prometheus 官方文档：https://prometheus.io/docs/
- Grafana 官方文档：https://grafana.com/docs/
- prometheus-fastapi-instrumentator：https://github.com/trallnag/prometheus-fastapi-instrumentator
- MinIO Python SDK：https://min.io/docs/minio/linux/developers/python/minio-py.html

### 11.2 相关文档

- 后端设计方案：`docs/backend-plans/后端开发设计方案.md`
- 存储接口定义：`backend/app/core/storage/interface.py`
- MinIO 实现：`backend/app/core/storage/minio.py`

---

**文档版本历史**：
- v1.0 (2026-09-10): 初始版本