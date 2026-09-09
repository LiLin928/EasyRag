# EasyRAG Phase 4 开发方案设计文档

> **日期**: 2026-08-31
> **版本**: v1.0
> **状态**: 已批准，待实施
> **周期**: 6 周（3 Phase）

---

## 一、背景与现状

### 1.1 当前进度汇总

| 子项目 | 进度 | 状态 | 关键成果 |
|--------|------|------|----------|
| **A. RBAC + 安全加固** | 95% | 🟢 基本完成 | 多用户 RBAC、审计日志、速率限制框架 |
| **B. 存储与运维** | 40% | 🟡 进行中 | 配置就绪，MinIO 切换未开始 |
| **C. 异步与扩展** | 90% | 🟢 基本完成 | PostgreSQL 队列、Worker、SSE 事件流 |
| **D. 功能增强** | 30% | 🔴 待启动 | 仅基础框架，核心功能未实现 |

### 1.2 技术债务

- A: 文件 magic number 校验缺失
- B: 本地存储无法支撑多 Worker 部署
- C: Worker 多实例并发需压测验证
- D: 依赖 C 完成后才能启动

### 1.3 架构演进

```
Phase 3 (已完成)
├── Redis ARQ → PostgreSQL 队列 ✅
├── Redis Stream → PostgreSQL events ✅
└── Single Worker → Multi Worker (待验证)

Phase 4 (本方案)
├── Local Storage → MinIO 对象存储
├── 单点部署 → 多 Worker + 监控告警
└── 基础解析 → MinerU 精准解析 + 代码沙箱
```

---

## 二、总体策略

### 2.1 核心原则

> **基础设施先行，功能后置**

### 2.2 Phase 划分

```
Phase 1 (Week 1-2): 基础设施收尾 + 存储切换
├── Task A-1: 文件 magic number 校验
├── Task B-1: MinIO 切换
├── Task B-2: 备份脚本
└── Task C-1: Worker 多实例部署验证

Phase 2 (Week 3-4): 生产就绪加固
├── Task B-3: 监控告警
├── Task C-2: 性能调优 + 压力测试
└── Task D-1: MinerU 精准解析集成

Phase 3 (Week 5-6): 功能扩展
├── Task D-2: 代码沙箱池
├── Task D-3: Webhook 触发器
└── Task D-4: 版本 diff 可视化
```

### 2.3 依赖关系

```
A-1 ──┬──> B-1 ──┬──> C-1 ──┬──> D-1
      │          │          │
      └──> B-2 ──┘          ├──> D-2
      │                     │
      └──> B-3 ─────────────┼──> D-3
                            │
                            └──> D-4
```

---

## 三、详细设计

### Phase 1: 基础设施收尾 + 存储切换 (Week 1-2)

#### Task A-1: 文件 Magic Number 校验

**目标**: 防止恶意文件上传，验证文件真实类型

**实现文件**:
- `backend/app/core/file_validator.py` - 新增
- `backend/app/api/v2/assets.py` - 修改上传接口

**技术方案**:

```python
# file_validator.py
MAGIC_SIGNATURES = [
    (b"%PDF", "application/pdf"),
    (b"PK\x03\x04", "application/zip"),  # docx/xlsx
    (b"\xd0\xcf\x11\xe0", "application/msword"),  # doc (OLE)
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
]

def detect_file_type(content: bytes) -> str | None:
    """根据 magic number 检测 MIME 类型"""
    
def validate_file_magic(content: bytes, allowed: set[str]) -> None:
    """校验文件类型是否在允许列表内"""
```

**验收标准**:
- [ ] 支持 PDF/Word/Excel/图片类型检测
- [ ] 上传接口拒绝类型不符的文件
- [ ] 单元测试覆盖率 > 80%

---

#### Task B-1: MinIO 存储切换

**目标**: 将本地文件存储迁移到 MinIO，支持多 Worker 共享

**实现文件**:
- `backend/app/services/storage.py` - 新增（抽象存储层）
- `backend/app/services/minio_client.py` - 新增
- `backend/app/config.py` - 修改配置
- `backend/app/api/v2/assets.py` - 修改上传/下载接口

**技术方案**:

```python
# storage.py - 抽象接口
class StorageInterface(Protocol):
    async def upload(self, key: str, content: bytes) -> str: ...
    async def download(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...

# minio_client.py - MinIO 实现
class MinioStorage:
    def __init__(self, endpoint, access_key, secret_key, bucket):
        self.client = Minio(...)
    
# config.py
class Settings:
    storage_type: str = "minio"  # local | minio
    minio_endpoint: str = Field(...)
    minio_access_key: str = Field(...)
    minio_secret_key: str = Field(...)
    minio_bucket: str = "easyrag"
    minio_secure: bool = True
```

**迁移策略**:
1. 双写期：新文件写 MinIO，同时保留本地
2. 读优先：MinIO 不存在则回退本地
3. 切换后：后台任务迁移存量文件

**验收标准**:
- [ ] 支持本地/MinIO 无缝切换（配置化）
- [ ] 文件上传/下载/删除功能正常
- [ ] 多 Worker 可共享存储

---

#### Task B-2: 备份脚本

**目标**: 自动化 PostgreSQL 和 MinIO 备份

**实现文件**:
- `backend/scripts/backup_db.py` - 数据库备份
- `backend/scripts/backup_storage.py` - MinIO 备份
- `backend/scripts/backup.sh` - 统一入口
- `docker-compose.backup.yml` - 定时任务

**技术方案**:

```bash
# backup.sh
#!/bin/bash
# 1. PostgreSQL 备份 (pg_dump)
pg_dump $DATABASE_URL | gzip > backup/db_$(date +%Y%m%d).sql.gz

# 2. MinIO 备份 (mc mirror)
mc mirror minio/easyrag backup/minio/

# 3. 清理旧备份 (保留 7 天)
find backup/db_*.sql.gz -mtime +7 -delete

# 4. 上传至对象存储（可选）
mc cp backup/db_$(date +%Y%m%d).sql.gz backup/minio/
```

**验收标准**:
- [ ] 每日自动备份
- [ ] 保留 7 天历史
- [ ] 支持一键恢复

---

#### Task C-1: Worker 多实例部署验证

**目标**: 验证 PostgreSQL 队列在多 Worker 下的并发安全

**实现文件**:
- `backend/scripts/start_workers.py` - 多 Worker 启动器
- `backend/tests/test_pg_queue_concurrent.py` - 并发测试

**技术方案**:

```python
# start_workers.py
import subprocess
import sys

def start_workers(count: int = 3):
    """启动多个 Worker 进程"""
    procs = []
    for i in range(count):
        proc = subprocess.Popen([
            sys.executable, "-m", "app.worker.pg_worker_main",
            "--worker-id", f"worker-{i}",
            "--fast-interval", "0.1",
            "--slow-interval", "5.0"
        ])
        procs.append(proc)
    return procs
```

**测试场景**:
1. 并发 dequeue：100 任务 / 3 Worker，验证无重复执行
2. 故障恢复：Worker 崩溃后任务重新分配
3. 负载均衡：任务均匀分布到各 Worker

**验收标准**:
- [ ] 3 Worker 并发执行 100 任务无重复
- [ ] Worker 崩溃后任务自动重试
- [ ] 断点恢复（checkpoint）正常工作

---

### Phase 2: 生产就绪加固 (Week 3-4)

#### Task B-3: 监控告警

**目标**: Worker 健康检查 + 异常告警

**实现文件**:
- `backend/app/api/v2/health.py` - 健康检查端点
- `backend/app/core/metrics.py` - 指标收集
- `backend/scripts/health_check.py` - 告警脚本

**技术方案**:

```python
# health.py
@router.get("/health/workers")
async def worker_health():
    """Worker 健康状态"""
    return {
        "pending_jobs": await PGJobQueue.count_pending(),
        "running_jobs": await PGJobQueue.count_running(),
        "workers": [
            {"id": w.worker_id, "status": w.status, "last_heartbeat": w.updated_at}
            for w in await PGJobQueue.list_workers()
        ]
    }

# metrics.py
METRICS = {
    "queue_pending": Gauge("queue_pending_jobs"),
    "queue_running": Gauge("queue_running_jobs"),
    "worker_executions": Counter("worker_executions_total"),
}
```

**告警规则**:
- 待处理任务 > 100 告警
- Worker 心跳超时 > 5 分钟告警
- 任务失败率 > 10% 告警

**验收标准**:
- [ ] `/health/workers` 返回实时状态
- [ ] Prometheus metrics 暴露
- [ ] 告警通知（日志/邮件/钉钉）

---

#### Task C-2: 性能调优 + 压力测试

**目标**: 验证系统可支撑 100 并发执行

**实现文件**:
- `backend/tests/stress/test_concurrent_workflows.py` - 压力测试
- `backend/scripts/benchmark.py` - 性能基准

**测试方案**:

```python
# test_concurrent_workflows.py
@pytest.mark.asyncio
async def test_100_concurrent_workflows():
    """100 并发工作流执行测试"""
    tasks = [
        enqueue_workflow_task(f"wf-{i}", {}, "test", None)
        for i in range(100)
    ]
    execution_ids = await asyncio.gather(*tasks)
    
    # 等待全部完成
    await wait_all_complete(execution_ids, timeout=300)
    
    # 验证：无重复执行、无丢失
    assert len(set(execution_ids)) == 100
```

**性能指标**:
| 指标 | 目标 |
|------|------|
| 并发执行 | 100 |
| 平均延迟 | < 2s (enqueue → start) |
| 吞吐量 | > 50/s |
| DB QPS | < 1000 |

**调优项**:
- Worker poll_interval 自适应
- 数据库连接池调优
- 事件表分区（按月）

**验收标准**:
- [ ] 100 并发任务全部成功
- [ ] 无重复执行、无任务丢失
- [ ] 系统资源占用 < 80%

---

#### Task D-1: MinerU 精准解析集成

**目标**: 接入 MinerU 实现高质量文档解析

**实现文件**:
- `backend/app/core/parser/mineru_adapter.py` - MinerU 适配器
- `backend/app/services/parse_service.py` - 修改解析服务
- `backend/app/api/v2/parse_tasks.py` - 解析任务 API

**技术方案**:

```python
# mineru_adapter.py
class MinerUParser:
    """MinerU 文档解析适配器"""
    
    async def parse(self, file_path: str) -> ParsedDocument:
        """调用 MinerU 服务解析文档"""
        # 支持 PDF/DOCX/图片
        # 返回结构化内容：标题、段落、表格、图片
        
class ParsedDocument:
    title: str
    sections: List[Section]  # 章节层级
    tables: List[Table]      # 表格
    images: List[Image]      # 图片
    metadata: Dict           # 元数据

# parse_service.py
async def parse_document(doc_id: str, parser: str = "mineru"):
    if parser == "mineru":
        return await MinerUParser().parse(file_path)
    elif parser == "legacy":
        return await LegacyParser().parse(file_path)
```

**部署方案**:
- MinerU 作为独立服务（Docker）
- 通过 HTTP API 调用
- 支持 GPU 加速

**验收标准**:
- [ ] PDF 解析准确率 > 95%
- [ ] 支持表格、图片提取
- [ ] 解析任务异步执行（入队）

---

### Phase 3: 功能扩展 (Week 5-6)

#### Task D-2: 代码沙箱池

**目标**: 安全执行用户代码（Python/JavaScript）

**实现文件**:
- `backend/app/core/tools/sandbox.py` - 沙箱执行器
- `backend/app/services/code_execution_service.py` - 执行服务

**技术方案**:

```python
# sandbox.py
class CodeSandbox:
    """代码沙箱执行器"""
    
    def __init__(self, timeout: int = 30, memory_limit: str = "128m"):
        self.timeout = timeout
        self.memory_limit = memory_limit
    
    async def execute_python(self, code: str, inputs: dict) -> ExecutionResult:
        """在 Docker 容器中执行 Python 代码"""
        # 使用 firejail + seccomp 隔离
        # 限制网络、文件系统访问
        
    async def execute_javascript(self, code: str, inputs: dict) -> ExecutionResult:
        """执行 Node.js 代码"""
```

**安全策略**:
- Docker 容器隔离
- 资源限制（CPU/内存/时间）
- 禁用网络访问
- 只读文件系统

**验收标准**:
- [ ] 支持 Python/Node.js 执行
- [ ] 资源隔离（CPU/内存/时间）
- [ ] 危险操作拦截

---

#### Task D-3: Webhook 触发器

**目标**: 外部系统触发工作流执行

**实现文件**:
- `backend/app/models/webhook.py` - Webhook 模型
- `backend/app/api/v2/webhooks.py` - API
- `backend/app/services/webhook_service.py` - 服务

**技术方案**:

```python
# webhook.py
class Webhook(Base):
    """Webhook 配置"""
    workflow_id: UUID
    secret: str  # 签名密钥
    enabled: bool
    filters: JSON  # 触发条件过滤
    
# webhooks.py
@router.post("/webhooks/{webhook_id}")
async def webhook_trigger(webhook_id: str, request: Request):
    """接收外部 Webhook 触发"""
    # 1. 验证签名
    # 2. 解析 payload
    # 3. 匹配过滤条件
    # 4. 入队执行工作流
    exec_id = await enqueue_workflow_task(
        workflow_id=webhook.workflow_id,
        inputs=payload,
        trigger="webhook",
        user_id=None
    )
```

**安全机制**:
- HMAC-SHA256 签名验证
- IP 白名单
- 速率限制

**验收标准**:
- [ ] 支持自定义 secret
- [ ] 请求签名验证
- [ ] 支持过滤条件配置

---

#### Task D-4: 版本 Diff 可视化

**目标**: 对比工作流版本差异

**实现文件**:
- `backend/app/services/version_diff_service.py` - Diff 服务
- `backend/app/api/v2/workflows.py` - Diff API

**技术方案**:

```python
# version_diff_service.py
class VersionDiff:
    """工作流版本对比"""
    
    def compare(self, v1: WorkflowVersion, v2: WorkflowVersion) -> DiffResult:
        """对比两个版本差异"""
        return {
            "nodes_added": [...],    # 新增节点
            "nodes_removed": [...],  # 删除节点
            "nodes_modified": [...], # 修改节点
            "edges_changed": [...],  # 连线变化
        }

# Diff 算法
# 1. 按 node.id 建立映射
# 2. 对比节点属性（type, config, position）
# 3. 对比 edges（source, target, condition）
```

**前端展示**:
- 节点增删改高亮
- 属性变更对比
- 并排/叠加视图

**验收标准**:
- [ ] 节点级 diff 检测
- [ ] 属性变更追踪
- [ ] API 返回结构化 diff

---

## 四、数据库变更

### 4.1 MinIO 配置表

```sql
-- 文件存储记录表（如使用 MinIO）
ALTER TABLE documents ADD COLUMN storage_key VARCHAR(255);
ALTER TABLE documents ADD COLUMN storage_type VARCHAR(20) DEFAULT 'local';
```

### 4.2 Webhook 表

```sql
CREATE TABLE webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES workflows(id),
    secret VARCHAR(255) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    filters JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 4.3 解析任务扩展

```sql
ALTER TABLE parse_tasks ADD COLUMN parser_type VARCHAR(20) DEFAULT 'legacy';
ALTER TABLE parse_tasks ADD COLUMN mineru_job_id VARCHAR(100);
```

---

## 五、部署清单

### 5.1 Phase 1 部署

```bash
# 1. 启动 MinIO
docker run -d --name minio \
  -p 9000:9000 -p 9001:9001 \
  -v minio-data:/data \
  minio/minio server /data --console-address ":9001"

# 2. 创建 bucket
mc alias set local http://localhost:9000 minioadmin minioadmin
mc mb local/easyrag

# 3. 启动多 Worker
python -m scripts.start_workers --count 3

# 4. 验证
pytest tests/test_pg_queue_concurrent.py -v
```

### 5.2 Phase 2 部署

```bash
# 1. 启动 MinerU 服务
docker run -d --name mineru \
  -p 8000:8000 \
  --gpus all \
  mineru/mineru:latest

# 2. 配置 Prometheus 监控
# 3. 启动告警规则
```

### 5.3 Phase 3 部署

```bash
# 1. 启动代码沙箱
docker run -d --name sandbox \
  -p 50051:50051 \
  easyrag/sandbox:latest

# 2. 验证 Webhook
# 3. 验证版本 diff
```

---

## 六、风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| MinIO 迁移数据丢失 | 中 | 高 | 双写期 + 备份验证 |
| PostgreSQL 队列性能瓶颈 | 低 | 高 | 压力测试 + 分区 |
| MinerU 解析失败 | 中 | 中 | fallback 到 legacy 解析 |
| 代码沙箱逃逸 | 低 | 高 | Docker + seccomp + 资源限制 |

---

## 七、验收标准汇总

### Phase 1
- [ ] 文件上传拒绝非法类型
- [ ] MinIO 存储读写正常
- [ ] 3 Worker 并发无重复执行
- [ ] 每日自动备份成功

### Phase 2
- [ ] 100 并发任务全部成功
- [ ] Worker 健康检查 API 正常
- [ ] MinerU 解析准确率 > 95%

### Phase 3
- [ ] 代码沙箱安全执行
- [ ] Webhook 签名验证正常
- [ ] 版本 diff API 返回正确

---

## 八、附录

### 8.1 依赖版本

- Python: 3.10+
- PostgreSQL: 14+
- MinIO: RELEASE.2024-01-01
- MinerU: latest

### 8.2 参考文档

- `docs/superpowers/specs/2026-08-31-postgresql-queue-design.md`
- `docs/superpowers/specs/2026-08-28-rbac-security-hardening-design.md`
- `docs/superpowers/specs/2026-08-28-phase3-async-scalability-design.md`

---

*文档结束*
