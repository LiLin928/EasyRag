# Langfuse 集成指南

## ✅ 集成状态

- **依赖**: `langfuse>=3.0` ✅
- **配置**: `.env` 已配置 ✅
- **代码**: `app/providers/trace/factory.py` ✅
- **服务**: `http://192.168.137.13:3030` ✅

---

## 🔧 配置（已完成）

### `.env` 文件

```bash
# Tracing（启用 Langfuse）
TRACING_PROVIDER=langfuse
LANGFUSE_PUBLIC_KEY=pk-lf-ffd02570-0b00-4219-bd60-6181a86ceba7
LANGFUSE_SECRET_KEY=sk-lf-9fe1cc61-e8a6-4f1d-b922-e6a903299f37
LANGFUSE_HOST=http://192.168.137.13:3030
```

---

## 📝 使用方法

### 1. 在 LangChain LLM 调用中使用

```python
from app.providers.trace.factory import get_tracing_callbacks
from app.providers.langchain_factory import build_chat_model

# 构建 LLM
llm = build_chat_model(model_config)

# 调用时注入 callbacks
response = await llm.ainvoke(
    "你的问题",
    config={"callbacks": get_tracing_callbacks()}
)
```

### 2. 自动追踪（应用启动时）

应用启动时会自动调用 `configure_tracing()`，根据 `TRACING_PROVIDER` 配置：

- `langfuse` - 使用 Langfuse 追踪
- `langsmith` - 使用 LangSmith 追踪
- `none` - 禁用追踪

---

## 🎯 追踪的功能

### 已自动追踪

| 功能 | 追踪内容 |
|------|---------|
| **LLM 调用** | Prompt、Completion、Token 数、延迟 |
| **Chat 模型** | 多轮对话、消息历史 |
| **Embedding** | 文本向量化的维度和数量 |
| **RAG 检索** | 检索上下文、相似度分数 |

### 需手动添加 callbacks

以下功能需要在调用时注入 `get_tracing_callbacks()`：

1. **自定义 LLM 调用**
2. **Agent 执行**
3. **工具调用**

---

## 🔍 查看追踪数据

### 访问 Langfuse UI

```
http://192.168.137.13:3030
```

### 功能

- **Traces** - 查看完整的调用链
- **Sessions** - 用户会话追踪
- **Generations** - LLM 生成记录
- **Scores** - 对回复评分
- **Datasets** - 收集数据用于微调

---

## 📊 示例：Chat API 追踪

### 请求

```bash
curl -X POST http://localhost:8000/api/v2/chat/sessions/{id}/messages \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"content": "什么是 RAG？"}'
```

### Langfuse 追踪

```
Trace: chat-session-{id}
├── Generation: llm-call
│   ├── Prompt: "什么是 RAG？"
│   ├── Completion: "RAG 是检索增强生成..."
│   ├── Tokens: 150
│   └── Duration: 2.3s
└── Metadata
    ├── Model: gpt-4
    └── User: user123
```

---

## ⚙️ 高级配置

### 自定义 Trace 名称

```python
from langfuse.decorators import observe

@observe()
async def my_function():
    # 这个函数的执行会被追踪
    result = await llm.ainvoke(...)
    return result
```

### 添加自定义 Metadata

```python
from app.providers.trace.factory import _langfuse_handler

if _langfuse_handler:
    _langfuse_handler.trace.update(metadata={
        "custom_field": "value"
    })
```

---

## 🔄 切换 Tracing 提供者

### Langfuse（当前）

```bash
TRACING_PROVIDER=langfuse
LANGFUSE_PUBLIC_KEY=pk-xxx
LANGFUSE_SECRET_KEY=sk-xxx
LANGFUSE_HOST=http://192.168.137.13:3030
```

### LangSmith（云服务）

```bash
TRACING_PROVIDER=langsmith
LANGSMITH_API_KEY=lsv2_pt_xxx
LANGSMITH_PROJECT=easyrag
```

### 禁用

```bash
TRACING_PROVIDER=none
```

---

## 🧪 验证集成

### 1. 启动后端

```bash
cd D:/4-MyProject/EasyRag/backend
uv run uvicorn app.main:app --reload
```

### 2. 执行 LLM 调用

```bash
# 通过 Chat API 或直接调用
curl -X POST http://localhost:8000/api/v2/chat \
  -H "Authorization: Bearer {token}" \
  -d '{"message": "Hello"}'
```

### 3. 查看 Langfuse

访问 `http://192.168.137.13:3030`，应该看到新的 Trace 记录。

---

## 📚 参考文档

- [Langfuse 官方文档](https://langfuse.com/docs)
- [LangChain Callbacks](https://python.langchain.com/docs/modules/callbacks/)
- `app/providers/trace/factory.py` - 集成代码

---

## 🐛 常见问题

### Q: 没有看到追踪数据？

**A**: 检查：
1. `.env` 中 `TRACING_PROVIDER=langfuse`
2. Langfuse 服务运行：`curl http://192.168.137.13:3030`
3. API Key 正确
4. 调用时注入了 callbacks：`config={"callbacks": get_tracing_callbacks()}`

### Q: Token 统计不准确？

**A**: 确保 LLM 返回了 token 使用信息：
```python
response = await llm.ainvoke(..., config={"callbacks": callbacks})
print(response.response_metadata)  # 应包含 token_usage
```

### Q: 延迟太高？

**A**: Langfuse 使用异步上传，不影响 LLM 调用性能。查看 `LANGFUSE_HOST` 是否可快速访问。

---

**配置日期**: 2026-09-09
**集成状态**: ✅ 已启用