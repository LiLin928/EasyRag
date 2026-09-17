# MCP 工具调用错误排查记录

## 问题现象

```
Found AIMessages with tool_calls that do not have a corresponding ToolMessage
```

Agent 调用 MCP 工具时持续报错。

## 根本原因

**Python 环境问题**：uvicorn 服务使用了全局 Python 环境，而不是虚拟环境 `.venv`。

### 问题链

1. 全局环境没有安装 `langchain-mcp-adapters` 包
2. MCP 工具加载失败：`No module named 'langchain_mcp_adapters'`
3. 工具执行抛出异常
4. LangGraph 无法生成 ToolMessage
5. 前端重试导致历史消息累积
6. 恶性循环：每次重试都加载更多失败的工具调用记录

## 解决方案

### 1. 正确启动服务

**使用 `uv run`**（推荐）：

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**或使用虚拟环境**：

```bash
cd backend
.venv\Scripts\activate  # Windows
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. 清除历史记录

如果已经累积了错误历史，调用 API 清除：

```bash
curl -X DELETE http://localhost:8000/api/v2/agents/{agent_id}/history \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. 验证

测试脚本验证 MCP 工具是否正常：

```bash
cd backend
uv run python -c "
from langchain_mcp_adapters.client import MultiServerMCPClient
print('[OK] langchain_mcp_adapters 可以导入')
"
```

## 已提交的修复

1. **Commit 8b26640**: 修复工具参数默认值问题
2. **Commit 4d31279**: 添加清除历史记录 API

## 预防措施

1. **始终使用 `uv run` 启动服务**
2. **遇到错误时先清除历史记录再重试**
3. **前端优化：检测到特定错误时提示用户清除历史**

## 相关文件

- `backend/app/core/agent/tool_registry_lazy.py` - MCP 懒加载工具
- `backend/app/core/agent/tool_adapters/mcp_tools.py` - MCP 工具加载
- `backend/app/api/v2/agents.py` - 清除历史记录 API
- `backend/start_service.bat` - 正确启动服务的脚本