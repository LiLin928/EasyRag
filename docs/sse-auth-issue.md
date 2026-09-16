# SSE 连接失败问题分析

## 问题现象
前端报错："实时事件流连接失败"

## 根本原因

### 技术限制
**EventSource API 不支持自定义 Headers**

```javascript
// ❌ EventSource 不支持传递 Authorization
const eventSource = new EventSource(url)
// 无法添加 headers: { Authorization: 'Bearer token' }
```

### 实际错误
```bash
curl http://localhost:3000/api/v2/executions/test-id/stream
# 返回: {"code":40101,"message":"缺少认证信息","data":null}
```

### 后端要求
```python
# backend/app/api/v2/executions.py
async def stream(eid: str, me=Depends(get_current_user)):
    # ↑ 需要 Authorization header
```

---

## 解决方案

### 方案 1：使用 Fetch API 替代 EventSource（推荐）

**优势**：
- ✅ 支持自定义 headers
- ✅ 完全控制请求
- ✅ 兼容性好

**实现**：

```javascript
// 替代 EventSource
async function connectSSE(url, token) {
  const response = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'text/event-stream',
    },
  })

  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // 解析 SSE 事件
    const events = buffer.split('\\n\\n')
    buffer = events.pop() || ''

    for (const eventStr of events) {
      if (!eventStr.trim()) continue

      const lines = eventStr.split('\\n')
      let eventType = 'message'
      let data = ''

      for (const line of lines) {
        if (line.startsWith('event:')) {
          eventType = line.substring(6).trim()
        } else if (line.startsWith('data:')) {
          data = line.substring(5).trim()
        }
      }

      // 触发事件处理
      handleEvent(eventType, JSON.parse(data))
    }
  }
}
```

### 方案 2：在 URL 中传递 Token（不推荐）

```javascript
// 安全性较低
const url = `${baseUrl}/executions/${executionId}/stream?token=${token}`
const eventSource = new EventSource(url)
```

### 方案 3：修改后端跳过 SSE 认证（特定场景）

```python
# 仅用于开发环境
async def stream(eid: str, request: Request):
    # 从 query 参数获取 token
    token = request.query_params.get("token")
    # 或跳过认证
```

---

## 推荐实施

**方案 1** 是最佳选择，我将在前端实现基于 Fetch API 的 SSE 客户端。