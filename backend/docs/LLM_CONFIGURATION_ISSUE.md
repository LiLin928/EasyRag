# EasyRAG LLM 配置问题分析与解决方案

## 问题描述

用户在使用 Agent + MCP 工具时遇到错误：
```
Found AIMessages with tool_calls that do not have a corresponding ToolMessage
```

## 根本原因

### 1. LLM API 未配置

`.env` 文件中的 LLM 配置被注释掉：
```env
# LLM_DEFAULT_BASE_URL=https://api.openai.com/v1
# LLM_DEFAULT_API_KEY=your-api-key
```

导致：
- 系统默认尝试连接 OpenAI API
- 没有有效的 API Key
- 网络连接超时（可能需要代理）

### 2. 消息历史不一致

LangGraph/LangChain 要求消息历史完整：

**正常流程**:
```
User Message → AIMessage(tool_calls=[...]) → ToolMessage(result) → AIMessage(继续)
```

**你的情况**:
```
User Message → AIMessage(tool_calls=[...]) → [失败，没有 ToolMessage]
```

当工具执行失败且无法生成 ToolMessage 时，下次调用会验证失败。

## 解决方案

### 方案一：配置 LLM API（推荐）

1. **编辑 `.env` 文件**:

```env
# 方案 1：使用 OpenAI API（需要代理）
LLM_DEFAULT_BASE_URL=https://api.openai.com/v1
LLM_DEFAULT_API_KEY=sk-your-real-api-key

# 方案 2：使用国内 API（如智谱 AI、通义千问等）
LLM_DEFAULT_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
LLM_DEFAULT_API_KEY=your-zhipu-api-key

# 方案 3：使用本地模型（如 Ollama）
LLM_DEFAULT_BASE_URL=http://localhost:11434/v1
LLM_DEFAULT_API_KEY=ollama

# 配置默认模型
LLM_QA_MODEL=gpt-4  # 或 glm-4、qwen-max 等
LLM_FAST_MODEL=gpt-3.5-turbo  # 或 glm-3-turbo、qwen-turbo 等
```

2. **重启服务**:
```bash
cd backend
uv run uvicorn app.main:app --reload
```

### 方案二：修复消息历史问题（临时）

在 `backend/app/services/agent_service.py` 中，工具执行失败时应该返回 ToolMessage：

```python
# 当前代码（第 104-119 行）
async for ev in react.astream_events(...):
    # 处理事件...

# 改进：捕获所有异常，确保 ToolMessage 被添加
try:
    async for ev in react.astream_events(...):
        # ...
except Exception as e:
    # 即使失败，也要确保消息历史完整
    yield sse_event("error", {"code": 50001, "message": str(e)})
```

但这只是治标不治本，**根本问题是 LLM 配置缺失**。

### 方案三：清理消息历史

如果已经产生了不一致的消息历史，可以清理 checkpointer：

```sql
-- 连接数据库
psql -h 192.168.137.13 -U easyrag -d easyrag_v2

-- 清理 checkpoint 表
DELETE FROM checkpointer WHERE thread_id LIKE 'agent:%';
```

## 验证修复

1. **运行诊断脚本**:
```bash
cd backend
uv run python scripts/diagnose_mcp_connection.py
```

2. **检查输出**:
```
数据库: [OK]
Redis:  [OK]
LLM:    [OK]  ← 这个应该是 OK
MCP:    1/5 成功
```

3. **测试 Agent 对话**:
```bash
curl -X POST http://localhost:8000/api/v2/agents/{agent_id}/chat \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"question": "搜索今天长电科技的股票信息"}'
```

## MCP 工具说明

你的 DuckDuckGo MCP 工具已正常工作，提供 3 个工具：
- `search`: 搜索
- `fetch_content`: 获取网页内容
- `expand_link`: 展开短链接

其他 MCP 服务未启用（`status=off`），如需使用请在数据库中启用。

## 常见问题

### Q: 为什么 MCP 工具能用但 Agent 不行？

A: MCP 工具（DuckDuckGo）直接访问搜索引擎，不依赖 LLM。但 Agent 需要 LLM 来：
1. 决定调用哪个工具
2. 处理工具返回的结果
3. 生成最终回复

### Q: 配置国内 API 还是 OpenAI？

A: 取决于你的网络环境：
- 国内 API（智谱、通义等）：无需代理，速度快
- OpenAI：需要代理，但功能最强

### Q: 如何测试 LLM API 是否可用？

A: 使用 curl 测试：
```bash
curl -X POST https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer {api_key}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

## 总结

**核心问题**: LLM API 未配置
**错误表现**: 消息历史不一致验证失败
**解决方法**: 配置 `.env` 中的 LLM API 参数
**验证工具**: 使用 `diagnose_mcp_connection.py` 脚本

---

生成时间: 2026-09-17