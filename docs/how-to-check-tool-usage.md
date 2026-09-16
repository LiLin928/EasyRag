# 如何判断智能体是否使用了工具/MCP/技能

## 判断方法

### 方法1：查看工具调用提示（推荐）

修复后，前端会显示工具调用提示：

```
🔧 正在使用 skill_unnamed...
🔧 正在使用 search...
🔧 正在使用 fetch_content...
```

看到这个提示说明工具正在被调用。

### 方法2：查看回复内容

#### 工具调用成功的标志：

1. **天气查询**
   - 回复包含具体的温度、湿度、风力等数据
   - 数据来自 OpenWeatherMap API
   - 示例："北京今天天气：多云，气温约 26.9℃"

2. **技能调用（数学计算）**
   - 回复包含计算结果
   - 示例："1 + 100 = **101**"
   - 技能名称：skill_unnamed

3. **MCP 调用（DuckDuckGo 搜索）**
   - 回复包含搜索结果链接
   - 回复包含详细的信息内容
   - 示例："长电科技（600584）今日股价..."

#### 工具未调用的标志：

- 回复是通用的文本，不包含具体数据
- 回复说"我没有相关工具"
- 回复是猜测性的答案

### 方法3：使用测试脚本

```bash
cd backend
uv run python ../test_tool_usage.py
```

测试脚本会显示：
```
[工具调用] skill_unnamed
[参数] {}
[工具返回] ...
```

### 方法4：检查后端日志

查看后端控制台输出，会看到：
```
[Agent] Tool getWeather called with input: {...}
[Agent] Tool skill_unnamed called
[Agent] MCP search called with input: {'query': '...'}
```

---

## 常见工具类型

### 1. 自定义工具（Tools）
- **标识**：工具名称来自工具配置
- **示例**：查询天气工具（tool_unnamed）
- **用途**：调用外部 API 或执行特定功能

### 2. 技能（Skills）
- **标识**：工具名称以 `skill_` 开头或 `skill_unnamed`
- **示例**：数字相加计算（skill_unnamed）
- **用途**：激活特定的 prompt 模板和提示词

### 3. MCP 服务
- **标识**：工具名称来自 MCP 服务定义
- **示例**：`search`、`fetch_content`（DuckDuckGo）
- **用途**：调用 MCP 服务器提供的工具

---

## 测试示例

### 天气查询
```
问题：北京今天天气怎么样
预期：🔧 正在使用 tool_unnamed...
      北京今天天气：多云，气温约 26.9℃
```

### 技能调用
```
问题：计算 1+100
预期：🔧 正在使用 skill_unnamed...
      1 + 100 = **101**
```

### MCP 搜索
```
问题：帮我搜索长电科技的股票
预期：🔧 正在使用 search...
      🔧 正在使用 fetch_content...
      长电科技（600584）今日股价...
```

---

## 故障排查

### 如果看到"未知错误"

1. **检查模型配置**
   ```bash
   curl -H "Authorization: Bearer {token}" \
     http://localhost:8000/api/v2/agents/{agent_id}
   ```
   确认 `model` 是默认的 qa 模型（有 "(默认)" 标记）

2. **检查工具状态**
   ```bash
   # 检查 MCP 状态
   curl -H "Authorization: Bearer {token}" \
     http://localhost:8000/api/v2/mcps

   # 检查工具状态
   curl -H "Authorization: Bearer {token}" \
     http://localhost:8000/api/v2/tools

   # 检查技能状态
   curl -H "Authorization: Bearer {token}" \
     http://localhost:8000/api/v2/skills
   ```

3. **查看后端日志**
   ```bash
   # 使用测试脚本
   cd backend
   uv run python ../test_tool_usage.py
   ```

4. **刷新前端页面**
   - 清除浏览器缓存（Ctrl+Shift+R）
   - 重新加载页面

---

## 调试技巧

### 1. 查看完整的事件流

在浏览器控制台运行：
```javascript
// 监听所有 SSE 事件
const originalFetch = window.fetch;
window.fetch = function(...args) {
  return originalFetch.apply(this, args).then(response => {
    console.log('Fetch:', args[0]);
    return response;
  });
};
```

### 2. 检查网络请求

在浏览器开发者工具中：
1. 打开 Network 标签页
2. 过滤 `/agents/{id}/chat`
3. 查看请求和响应

### 3. 使用测试脚本验证

```bash
# 测试工具调用
uv run python test_tool_usage.py

# 测试技能
uv run python test_skill_report.py

# 测试天气工具
uv run python test_tool_defaults.py
```

---

## 总结

| 问题类型 | 判断方法 | 查看位置 |
|---------|---------|---------|
| 工具是否被调用 | 看到"🔧 正在使用..." | 前端聊天界面 |
| 调用是否成功 | 回复包含具体数据 | 前端聊天界面 |
| 调用失败 | 显示"未知错误" | 前端聊天界面 |
| 详细调试 | 查看事件流 | 测试脚本/控制台 |

**关键点**：
- ✅ 看到"🔧 正在使用..." = 工具正在调用
- ✅ 回复包含具体数据 = 调用成功
- ❌ 显示"未知错误" = 需要检查模型配置