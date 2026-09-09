# 研究发现：OpenSandbox 对接

## 1. 当前实现分析

### 1.1 现有 sandbox.py 功能

**文件位置**：`backend/app/core/tools/sandbox.py`

**核心功能**：
- 支持语言：Python 3.10、Node.js 18
- 资源限制：内存 (512MB)、CPU (1.0)、超时 (30s)
- 安全措施：只读文件系统、禁用网络、能力限制、PIDS 限制
- 代码审计：阻止危险操作 (`__import__`, `eval`, `exec`, `os.system`, `subprocess`)

**暴露接口**：
```python
class SandboxResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    error: Optional[str]

async def execute_code(
    language: str,
    code: str,
    inputs: Optional[dict] = None,
    timeout: int = 30,
    memory_limit_mb: int = 512
) -> SandboxResult
```

---

## 2. OpenSandbox 服务状态

### 2.1 虚拟机部署情况

**来源**：`docker-compose.yml.bak` 第 293-323 行

```yaml
opensandbox-server:
  image: opensandbox/server:latest
  ports: "8090:8090"
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
    - /lilin/EasyRAG/opensandbox-config.toml:/etc/opensandbox/config.toml
  environment:
    SANDBOX_CONFIG_PATH: /etc/opensandbox/config.toml

opensandbox-client:
  environment:
    OPEN_SANDBOX_DOMAIN: opensandbox-server:8090
    OPEN_SANDBOX_API_KEY: ${OPENSANDBOX_API_KEY:-easyrag2026}
```

### 2.2 服务状态验证

```bash
curl http://192.168.137.13:8090/health
# 响应: 200 OK
```

**结论**：OpenSandbox 服务已正常运行。

---

## 3. OpenSandbox API 研究

### 3.1 核心端点

| 端点 | 方法 | 用途 |
|------|------|------|
| `/sandboxes` | POST | 创建沙箱（异步，返回 202） |
| `/sandboxes/{id}` | GET | 获取沙箱状态 |
| `/sandboxes/{id}` | DELETE | 删除沙箱（204） |
| `/sandboxes/{id}/diagnostics/logs` | GET | 获取执行日志 |
| `/sandboxes/{id}/proxy/{port}/{path}` | ALL | 代理请求到沙箱内部 |

### 3.2 请求格式

**创建沙箱请求** (`CreateSandboxRequest`)：
```json
{
  "image": "python:3.10-alpine",  // 镜像名称
  "command": ["python", "/code/main.py"],  // 执行命令
  "env": {"KEY": "value"},  // 环境变量
  "resources": {
    "memory_mb": 512,
    "cpu": 1.0
  },
  "timeout_seconds": 30,
  "metadata": {"key": "value"}  // 自定义元数据
}
```

**创建沙箱响应** (`CreateSandboxResponse`)：
```json
{
  "sandbox_id": "sb_xxx",
  "status": "Creating"
}
```

### 3.3 沙箱生命周期状态

```
Creating → Running → Pausing ↔ Paused → Resuming → Running
                     ↓
                  Stopping → Terminated
                     ↓
                    Error
```

### 3.4 认证方式

- 需要 `X-Request-ID` header 用于请求追踪
- API Key 认证（从 docker-compose 看是 `OPEN_SANDBOX_API_KEY`）

### 3.5 执行流程（对比当前实现）

**当前自建实现**：
```
本地 docker run → 同步等待 → 获取输出 → 清理
```

**OpenSandbox 实现需要**：
```
POST /sandboxes → 轮询 GET /sandboxes/{id} → 获取 logs → DELETE
```

### 3.6 关键差异

| 特性 | 当前自建 | OpenSandbox |
|------|---------|-------------|
| 执行方式 | 同步 | 异步（需轮询） |
| 语言支持 | Python/NodeJS | 任意容器镜像 |
| 资源限制 | docker 参数 | API 请求体 |
| 生命周期 | 单次执行 | 完整管理 |
| 隔离位置 | 本机 | 虚拟机服务 |

---

## 4. 差异分析

### 4.1 接口对比

| 特性 | 当前自建实现 | OpenSandbox |
|------|-------------|-------------|
| 部署位置 | 本机 Docker | 虚拟机 HTTP API |
| 依赖 | 本地 Docker 环境 | 网络连接 + API Key |
| 隔离方式 | 直接 docker run | 远程服务隔离 |
| 配置方式 | 代码内配置 | 服务端配置 + 客户端参数 |

### 4.2 需要解决的问题

1. ~~**API 文档缺失**~~ ✅ 已获取 OpenAPI 规范
2. **认证机制**：需要在 HTTP 请求中添加 API Key
3. **异步轮询**：OpenSandbox 是异步模型，需要轮询状态
4. **兼容性**：确保现有 `execute_code()` 接口不变
5. **错误处理**：网络异常、服务不可用、超时的处理

---

## 5. 设计方案

### 5.1 架构设计

```
┌─────────────────┐      HTTP API      ┌──────────────────────┐
│  execute_code() │ ───────────────────▶│  OpenSandbox Client  │
│  (现有接口)      │                    │  (新增)               │
└─────────────────┘                    └──────────────────────┘
                                                  │
                                                  ▼
                                        ┌──────────────────────┐
                                        │  OpenSandbox Server  │
                                        │  192.168.137.13:8090 │
                                        └──────────────────────┘
```

### 5.2 配置项设计

```python
# config.py 新增
opensandbox_url: str = "http://192.168.137.13:8090"
opensandbox_api_key: str | None = None
opensandbox_timeout: int = 30
opensandbox_memory_mb: int = 512
opensandbox_cpu: float = 1.0
```

### 5.3 兼容层设计

**保持 `execute_code()` 接口不变**：
- 内部重构为调用 OpenSandbox API
- 将同步语义映射到异步轮询模型
- `SandboxResult` 结构保持不变

### 5.4 执行流程

```python
async def execute_code(language, code, inputs, timeout, memory_limit_mb):
    # 1. 创建沙箱（异步）
    sandbox = await create_sandbox(image, command, resources)

    # 2. 轮询状态直到完成/超时
    while sandbox.status != "Terminated":
        sandbox = await get_sandbox(sandbox.id)
        if timeout_exceeded:
            await delete_sandbox(sandbox.id)
            return SandboxResult(error="timeout")

    # 3. 获取日志
    logs = await get_sandbox_logs(sandbox.id)

    # 4. 清理
    await delete_sandbox(sandbox.id)

    # 5. 返回结果
    return SandboxResult(
        stdout=logs.stdout,
        stderr=logs.stderr,
        exit_code=sandbox.exit_code,
        execution_time_ms=...
    )
```

---

## 6. 实施计划

### Phase 1: 配置与基础设施
- [ ] 在 `config.py` 添加 OpenSandbox 配置项
- [ ] 在 `.env.example` 添加示例配置
- [ ] 更新文档

### Phase 2: OpenSandbox 客户端实现
- [ ] 创建 `app/providers/sandbox/opensandbox_client.py`
- [ ] 实现异步 HTTP 客户端
- [ ] 实现沙箱生命周期管理（创建/轮询/删除）
- [ ] 实现日志获取

### Phase 3: 重构 sandbox.py
- [ ] 重构 `CodeSandbox` 使用 OpenSandbox 客户端
- [ ] 保持 `execute_code()` 接口不变
- [ ] 处理错误和超时

### Phase 4: 测试
- [ ] 更新单元测试（mock OpenSandbox API）
- [ ] 添加集成测试（真实调用虚拟机 OpenSandbox）
- [ ] 验证现有功能兼容性

---

## 7. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| OpenSandbox 服务不可用 | 代码执行失败 | 健康检查 + 错误提示 |
| 网络延迟 | 执行变慢 | 设置合理超时 |
| API 变更 | 兼容性问题 | 版本锁定 + 适配层 |
| 虚拟机资源不足 | 创建失败 | 监控 + 告警 |