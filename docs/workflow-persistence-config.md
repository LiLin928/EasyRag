# 工作流持久化配置说明

## ✅ 已完成配置

我已为您添加了工作流持久化和多实例支持的功能。

---

## 📋 配置说明

### .env 配置文件

```bash
# Workflow（持久化配置）
WORKFLOW_PERSISTENT=true   # 生产环境：PostgresSaver（持久化、多实例）
# WORKFLOW_PERSISTENT=false  # 开发环境：MemorySaver（简单、快速）
```

---

## 🔄 两种模式对比

### MemorySaver（开发环境）
- ✅ **优点**：
  - 简单、快速
  - 无需额外配置
  - 无 Windows 环境依赖问题
- ❌ **缺点**：
  - 进程内存储，重启丢失
  - 单实例，无法共享状态

### PostgresSaver（生产环境）
- ✅ **优点**：
  - 持久化存储
  - 多实例支持
  - 执行历史保存
  - 支持断点恢复
- ❌ **缺点**：
  - 需要额外配置
  - Windows 环境需要事件循环策略

---

## ⚠️ Windows 环境特殊配置

在 Windows 上使用 PostgresSaver 需要设置事件循环策略：

### 方法 1：在 main.py 启动时设置（推荐）

```python
# backend/app/main.py
import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

### 方法 2：在启动命令中设置

```bash
# Windows PowerShell
$env:PYTHONASYNCIODEBUG=1
uv run uvicorn app.main:app --reload
```

---

## 🚀 使用建议

### 开发阶段
```bash
# .env
WORKFLOW_PERSISTENT=false
```
- 使用 MemorySaver
- 快速迭代，无需数据库依赖
- 适合本地开发

### 生产部署
```bash
# .env
WORKFLOW_PERSISTENT=true
```
- 使用 PostgresSaver
- 持久化、多实例支持
- 执行历史可追溯

---

## 📝 实现细节

### 配置文件
- `backend/app/config.py` - Settings 类添加 `workflow_persistent` 字段
- `backend/.env` - 环境变量配置

### 核心代码
- `backend/app/core/agent/memory.py` - Checkpointer 工厂
  - 自动根据配置选择
  - 失败时自动降级到 MemorySaver

---

## ✅ 已测试验证

- ✅ MemorySaver 工作正常
- ✅ 配置切换正常
- ⏳ PostgresSaver 需要 Windows 事件循环策略设置

---

## 📚 后续步骤

1. **添加 Windows 事件循环策略**（如果要在 Windows 上使用持久化）
2. **重启后端服务**
3. **测试工作流执行**
4. **验证持久化功能**

---

**配置已完成！**您现在可以根据环境选择合适的模式。