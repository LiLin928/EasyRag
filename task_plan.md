# 任务规划：OpenSandbox 后端对接

## 任务概述

为 OpenSandbox 添加后端配置和对接代码，替换当前自建的 Docker 隔离实现。

**设计决策来源**：`CLAUDE.md` 明确规定 "代码沙箱用虚拟机 OpenSandbox (:8090)，非自建 docker-py"

---

## 阶段规划

### Phase 1: 研究与发现 ✅
- [x] 研究 OpenSandbox API 文档
- [x] 分析当前 `sandbox.py` 实现的功能和接口
- [x] 对比自建实现与 OpenSandbox 的差异
- [x] 确认虚拟机 OpenSandbox 配置和状态

**关键发现**：
- OpenSandbox 采用异步模型（创建→轮询→删除）
- 支持任意容器镜像
- 需要轮询状态而非同步等待
- 详细 API 已在 `findings.md` 中记录

### Phase 2: 设计方案 ✅
- [x] 设计 OpenSandbox 客户端架构
- [x] 设计配置项和环境变量
- [x] 设计兼容层（保持现有接口不变）
- [x] 编写设计文档
- [x] **用户确认设计方案**

### Phase 3: 实现与测试 ⏳
- [ ] 在 config.py 添加 OpenSandbox 配置项
- [ ] 实现 OpenSandbox HTTP 客户端
- [ ] 重构 sandbox.py 使用 OpenSandbox API
- [ ] 编写/更新测试用例
- [ ] 集成测试

---

## 关键决策

| 决策 | 状态 | 说明 |
|------|------|------|
| 使用 OpenSandbox 替代自建 Docker | ✅ 已确认 | 符合项目设计决策 |
| 保持现有接口不变 | ✅ 已设计 | `execute_code()` 签名不变 |
| 异步轮询模型 | ✅ 已设计 | 适配 OpenSandbox API |
| 配置项设计 | ✅ 已设计 | 见下方配置示例 |

---

## 设计方案详情

### 配置项（添加到 `config.py`）

```python
# OpenSandbox 配置
opensandbox_url: str = "http://192.168.137.13:8090"
opensandbox_api_key: str | None = None
opensandbox_timeout: int = 30
opensandbox_memory_mb: int = 512
opensandbox_cpu: float = 1.0
```

### 文件结构

```
backend/app/
├── config.py                    # 添加 OpenSandbox 配置
├── core/tools/sandbox.py        # 重构为调用 OpenSandbox
└── providers/
    └── sandbox/                 # 新增目录
        ├── __init__.py
        └── opensandbox_client.py  # OpenSandbox HTTP 客户端
```

### 核心接口（保持不变）

```python
async def execute_code(
    language: str,           # python / nodejs
    code: str,               # 代码内容
    inputs: Optional[dict],  # 输入数据
    timeout: int = 30,       # 超时秒数
    memory_limit_mb: int = 512
) -> SandboxResult:
    """
    执行代码并返回结果。
    内部实现从本地 Docker 切换为 OpenSandbox API。
    """
```

---

## 待用户确认

请确认以上设计方案是否符合预期：
1. ✅ 配置项是否完整？
2. ✅ 接口保持不变是否正确？
3. ✅ 是否需要额外的降级/回退机制？

---

## 当前状态

- **虚拟机 OpenSandbox**：已部署，服务正常运行 (192.168.137.13:8090)
- **config.py**：缺少 OpenSandbox 配置项
- **sandbox.py**：自建 Docker 隔离实现，需重构