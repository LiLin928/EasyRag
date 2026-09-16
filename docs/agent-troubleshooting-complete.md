# 智能体"未知错误"完整排查记录

## 问题现象

用户创建智能体"测试2"，询问"今天北京天气怎么样"，返回"未知错误"。

但：
- ✅ 工作流中使用 LLM 节点正常
- ✅ 工具单独测试正常
- ❌ 智能体对话失败

---

## 问题根源（三层问题）

### 问题1：模型配置错误

**现象**：`Error code: 401 - Authentication Fails, Your api key is invalid`

**原因**：
- 工作流使用 `build_chat_model(use="qa")` → 选择默认 qa 模型
- 智能体使用 `build_chat_model_by_name("deepseek-v4-flash")` → 指定模型
- `deepseek-v4-flash` 的 API Key 无效

**解决**：切换智能体使用 `deepseek-v4-pro`（默认 qa 模型）

```bash
curl -X PUT http://localhost:8000/api/v2/agents/{agent_id} \
  -H "Authorization: Bearer {token}" \
  -d '{"model":"deepseek-v4-pro"}'
```

---

### 问题2：工具名称格式错误

**现象**：`Error code: 400 - Invalid 'tools[0].function.name': string does not match pattern '^[a-zA-Z0-9_-]+$'`

**原因**：
- 工具名称："查询天气"（包含中文）
- DeepSeek API 要求：`^[a-zA-Z0-9_-]+$`（只能包含字母、数字、下划线、连字符）

**解决**：添加 `_sanitize_tool_name` 函数自动转换

```python
def _sanitize_tool_name(name: str, prefix: str = "tool") -> str:
    # 移除非法字符，替换为下划线
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    # 如果以数字开头，添加前缀
    if sanitized and sanitized[0].isdigit():
        sanitized = f'{prefix}_{sanitized}'
    # 如果为空，使用默认名称
    if not sanitized or sanitized == '_' * len(sanitized):
        sanitized = f'{prefix}_unnamed'
    return sanitized
```

---

### 问题3：工具参数默认值未生效

**现象**：工具调用时 `appid` 参数为空或 `'demo'`，导致 `401 Invalid API key`

**原因**：
1. 参数定义中未将默认值传递给 LLM
   ```python
   # 错误：所有参数都是必填
   fields = {p["n"]: (str, ...) for p in (t.params or [])}
   ```
2. 工具执行时未合并默认参数

**解决**：

#### 修复1：参数定义传递默认值给 LLM

```python
from pydantic import Field

fields = {}
for p in (t.params or []):
    param_name = p.get("n", "param")
    default_value = p.get("d", ...)  # 使用默认值
    fields[param_name] = (
        str,
        Field(default=default_value, description=f"参数 {param_name}")
    )
```

#### 修复2：工具执行时合并默认参数

```python
async def execute(tool, args: dict, timeout: int = 30, cache_key: Optional[str] = None):
    # 合并默认参数：工具定义中的默认值 + 用户传入的参数
    merged_args = {}
    for p in (tool.params or []):
        param_name = p.get("n")
        if param_name and p.get("d") is not None:
            merged_args[param_name] = p["d"]  # 先设置默认值
    merged_args.update(args)  # 再覆盖用户传入的值

    # 使用合并后的参数执行工具
    result = await _http(tool, merged_args, timeout)
    # ...
```

---

## 完整修复流程

### 步骤1：检查智能体配置

```bash
# 获取智能体信息
curl -H "Authorization: Bearer {token}" \
  http://localhost:8000/api/v2/agents

# 更新智能体模型
curl -X PUT http://localhost:8000/api/v2/agents/{agent_id} \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-pro"}'
```

### 步骤2：检查模型配置

```bash
# 获取模型列表
curl -H "Authorization: Bearer {token}" \
  http://localhost:8000/api/v2/settings/models

# 确认模型状态
# - def: true 的模型是默认模型
# - use: "qa" 用于对话
# - enabled: true 已启用
```

### 步骤3：测试工具调用

```python
# 测试脚本
import asyncio
from app.services.tool_service import execute_tool

async def test():
    # 只传必要参数，测试默认值是否生效
    result = await execute_tool(
        "tool_id",
        {"q": "Beijing"}  # 不传 appid，应该使用默认值
    )
    print(f"成功: {result['success']}")
    if result['success']:
        print(f"温度: {result['data']['main']['temp']}°C")

asyncio.run(test())
```

### 步骤4：测试智能体对话

```python
# 测试脚本
import asyncio
from app.services.agent_service import AgentService

async def test_agent():
    agent_id = "your_agent_id"
    question = "今天北京天气怎么样"
    user_id = "your_user_id"

    svc = AgentService()
    async for event in svc.chat(agent_id, question, user_id):
        print(event)

asyncio.run(test_agent())
```

---

## 验证结果

### 测试命令

```bash
cd backend
uv run python ../test_agent_full.py
```

### 预期输出

```
问题：今天北京天气怎么样
============================================================

[工具调用] {"tool": "tool_unnamed", "input": "{'q': 'Beijing', 'appid': '1564bd59e86f981289a646fb2c421a63', 'units': 'metric'}"}
[工具完成] 返回天气数据

智能体回复：北京今天多云，温度约27°C，湿度50%，风速约3.7 m/s...

============================================================
[完成] 对话完成

工具调用次数：1
```

---

## 关键差异对比

| 项目 | 工作流 | 智能体 |
|------|--------|--------|
| **模型获取** | `build_chat_model(use="qa")` | `build_chat_model_by_name(name)` |
| **选择方式** | 按**用途**找默认模型 | 按**名称**查找 |
| **工具名称** | 不受限制 | **必须符合正则** `^[a-zA-Z0-9_-]+$` |
| **参数默认值** | 不需要特殊处理 | **需要显式设置** |
| **API Key** | 使用默认模型的有效Key | 使用指定模型的Key |

---

## 最佳实践

### 1. 智能体配置
- ✅ 使用默认的 qa 模型（`def: true, use: "qa"`）
- ✅ 避免指定特定模型名称，除非确定 API Key 有效
- ✅ 定期检查模型配置状态

### 2. 工具配置
- ✅ 使用英文名称（符合 `^[a-zA-Z0-9_-]+$`）
- ✅ 设置合理的默认值
- ✅ 在描述中说明参数用途
- ✅ 测试时验证默认值是否生效

### 3. 错误排查
1. 查看具体错误信息（不要只看"未知错误"）
2. 检查工具是否单独测试成功
3. 检查模型配置和 API Key
4. 检查工具名称和参数格式
5. 使用测试脚本定位问题

### 4. 监控建议
- 记录智能体执行日志
- 监控工具调用次数和成功率
- 定期检查 API Key 有效性
- 设置告警机制

---

## 相关文件

- `backend/app/core/agent/tool_registry.py` - 工具注册和名称处理
- `backend/app/core/tools/executor.py` - 工具执行和参数合并
- `backend/app/services/agent_service.py` - 智能体服务
- `backend/app/providers/langchain_factory.py` - 模型工厂

---

## 总结

智能体"未知错误"问题是由三个独立但相关的问题组成的：

1. **模型配置错误**：智能体指定了无效的模型
2. **工具名称格式错误**：中文名称不符合 API 要求
3. **参数默认值未生效**：默认值未正确传递和合并

通过逐层排查和修复，最终实现：
- ✅ 智能体成功调用工具
- ✅ 正确使用默认参数
- ✅ 返回有效结果

**关键点**：工作流和智能体虽然都使用 LangChain，但获取模型和工具的方式不同，需要分别配置和验证。