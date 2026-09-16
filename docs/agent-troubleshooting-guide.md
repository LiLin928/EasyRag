# 智能体"未知错误"问题诊断与解决方案

## 问题诊断

### 1. 错误现象
- **智能体名称**：测试2
- **用户提问**：今天北京天气怎么样
- **返回结果**：抱歉，发生了错误：未知错误

### 2. 根本原因

通过测试脚本发现具体错误：

```
Error code: 401 - {'error': {'message': 'Authentication Fails, Your api key: ******** is invalid', 'type': 'authentication_error'}}
```

**问题：DeepSeek API Key 无效或过期**

智能体"测试2"使用的模型 `deepseek-v4-flash`，但该模型的 API Key 认证失败。

### 3. 验证工具本身

测试天气工具：
```bash
curl -X POST http://localhost:8000/api/v2/tools/{tool_id}/test \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"q":"Beijing","appid":"your_key","units":"metric"}'
```

**结果**：✅ 工具执行成功，返回了北京的天气数据（28.94°C，多云）

**结论**：工具配置正确，问题出在 LLM 模型配置。

---

## 解决方案

### 方案 1：更新 DeepSeek API Key（推荐）

1. **获取有效的 DeepSeek API Key**
   - 访问：https://platform.deepseek.com/
   - 注册并获取 API Key

2. **更新系统设置**
   - 访问前端：http://localhost:3000/settings
   - 找到"模型配置"部分
   - 编辑 `deepseek-v4-flash` 模型
   - 更新 API Key
   - 保存

3. **或者通过 API 更新**
   ```bash
   TOKEN=$(curl -s -X POST http://localhost:8000/api/v2/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"admin123"}' \
     | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

   curl -X PUT http://localhost:8000/api/v2/settings/models/deepseek-v4-flash \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "deepseek-v4-flash",
       "key": "YOUR_NEW_API_KEY"
     }'
   ```

### 方案 2：切换到其他模型

如果 DeepSeek API Key 无效，可以切换到其他可用的模型：

1. **检查可用模型**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v2/settings/models
   ```

2. **修改智能体配置**
   - 访问：http://localhost:3000/agents
   - 编辑智能体"测试2"
   - 在"模型"下拉框中选择其他可用的模型（如 `deepseek-v4-pro`）
   - 保存

3. **或者通过 API 修改**
   ```bash
   AGENT_ID="545d7c33-0a98-4af6-afc3-f73b0f282efb"

   curl -X PUT http://localhost:8000/api/v2/agents/$AGENT_ID \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "deepseek-v4-pro"
     }'
   ```

### 方案 3：使用 OpenAI API（如果有）

如果配置了 OpenAI API：

1. **更新模型配置**
   - 访问：http://localhost:3000/settings
   - 添加或启用 OpenAI 模型（如 `gpt-4o`, `gpt-3.5-turbo`）
   - 配置有效的 OpenAI API Key

2. **修改智能体使用 OpenAI 模型**
   - 编辑智能体
   - 选择 OpenAI 模型
   - 保存并测试

---

## 验证修复

### 1. 测试模型连接

```bash
# 测试模型是否可用
curl -X POST http://localhost:8000/api/v2/test-model \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "deepseek-v4-flash"}'
```

### 2. 重新测试智能体

访问智能体页面，重新提问："今天北京天气怎么样"

**预期结果**：
- 智能体调用天气工具
- 返回北京的天气信息（温度、湿度、风力等）

---

## 监控与日志

### 查看后端日志

```bash
# 如果后端在控制台运行，查看实时日志
# 或者配置日志文件

# 使用 Python 测试脚本
cd backend
uv run python ../test_agent_chat.py
```

### 日志示例

```
[Agent] Starting chat for agent 测试2, prompt: You are a helpful assistant...
[Agent] Agent 测试2 initialized with 1 tools
[Agent] React agent created successfully
[Agent] User question: 今天北京天气怎么样
[Agent] Tool getWeather called with input: {"city": "北京"}
[Agent] Tool getWeather output: {"temp": 28.94, "weather": "多云"}
```

---

## 常见问题

### Q1: 为什么工具测试成功，但智能体对话失败？

**A**: 工具执行是独立的，不依赖 LLM。智能体需要 LLM 来理解用户意图并决定调用哪个工具。如果 LLM API Key 无效，智能体无法启动。

### Q2: 如何判断是模型问题还是工具问题？

**A**:
1. 单独测试工具（使用 `/api/v2/tools/{id}/test`）
2. 查看错误信息（401 = 认证错误，500 = 服务器错误）
3. 检查模型配置（API Key、URL、Provider）

### Q3: 可以使用哪些模型？

**A**: 支持的模型类型：
- OpenAI（gpt-4o, gpt-3.5-turbo）
- DeepSeek（deepseek-v4-pro, deepseek-v4-flash）
- Azure OpenAI
- Ollama（本地模型）

---

## 总结

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 未知错误 | DeepSeek API Key 无效 | 更新 API Key 或切换模型 |
| 工具未调用 | LLM 无法理解意图 | 检查 prompt 和模型配置 |
| 执行超时 | 网络或 API 响应慢 | 增加超时时间或更换服务商 |

**建议**：
1. 定期检查 API Key 是否有效
2. 配置多个可用模型作为备用
3. 监控智能体执行日志
4. 使用测试脚本快速定位问题