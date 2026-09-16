# 前端 API 模式配置指南

## 当前配置

前端已切换到**真实 API 模式**，将从后端获取数据。

### 环境变量（`.env.development`）

```env
VITE_API_BASE=/api/v2
VITE_USE_MOCK=false
```

## 前提条件

### 1. 后端服务必须运行

```bash
# 检查后端服务状态
curl http://localhost:8000/

# 应该返回：
# {"code":0,"message":"success","data":{"service":"easyrag","status":"ok"}}
```

**启动后端服务**：
```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. 用户必须登录

真实 API 需要认证 token。访问前端应用时会自动跳转到登录页。

**默认管理员账号**：
- 用户名：`admin`
- 密码：`admin123`

### 3. 后端数据库有数据

确保后端数据库中有工具、技能、MCP 数据：

```bash
# 获取 token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | grep -o '"access_token":"[^"]*' \
  | cut -d'"' -f4)

# 检查数据
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v2/tools
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v2/skills
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v2/mcps
```

## 启动前端服务

```bash
cd frontend
pnpm dev
```

访问：**http://localhost:3000**

## 切换回 Mock 模式

如果后端未准备好，可以临时切换回 Mock 模式：

```bash
# 编辑 .env.development
VITE_USE_MOCK=true

# 重启前端
cd frontend
pnpm dev
```

## API 端点

前端会请求以下端点：

| 模块 | 端点 | 说明 |
|------|------|------|
| 工具 | `/api/v2/tools` | 工具列表 |
| 技能 | `/api/v2/skills` | 技能列表 |
| MCP | `/api/v2/mcps` | MCP 服务列表 |
| 工作流 | `/api/v2/workflows` | 工作流列表 |
| 知识库 | `/api/v2/knowledge` | 知识库列表 |

## 故障排查

### 问题 1：无法加载工具/技能/MCP

**检查步骤**：
1. 确认后端服务运行中
2. 确认已登录（浏览器 localStorage 中有 token）
3. 打开浏览器控制台查看错误信息
4. 检查 Network 面板的 API 请求状态

**解决方案**：
- 如果返回 401，重新登录
- 如果返回 500，检查后端日志
- 如果没有数据，在相应管理页面添加数据

### 问题 2：Token 过期

**现象**：API 请求返回 `code: 40101` 或 `40102`

**解决方案**：
- 前端会自动尝试刷新 token
- 如果刷新失败，会跳转到登录页
- 重新登录即可

### 问题 3：CORS 错误

**现象**：浏览器控制台显示 CORS 错误

**解决方案**：
后端已配置 CORS，允许 `localhost:3000`。如果仍有问题：

```python
# backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 数据格式

### 工具（Tool）

```json
{
  "id": "uuid",
  "name": "工具名称",
  "type": "HTTP",
  "desc": "描述",
  "sig": "函数签名",
  "enabled": true,
  "params": [],
  "auth": {"mode": "none", "key": ""},
  "config": {},
  "createdAt": "2026-09-16T..."
}
```

### 技能（Skill）

```json
{
  "id": "uuid",
  "ico": "🔢",
  "name": "技能名称",
  "scope": "custom",
  "ver": "1.0.0",
  "desc": "描述",
  "trigger": "触发条件",
  "prompt": "系统提示词",
  "tools": [],
  "docs": [],
  "wfs": [],
  "examples": [],
  "scripts": []
}
```

### MCP

```json
{
  "id": "uuid",
  "name": "服务名称",
  "tp": "stdio",
  "cmd": "启动命令",
  "status": "on",
  "toolCount": 5,
  "env": [],
  "timeout": 30
}
```

## 开发建议

1. **优先使用真实 API**：确保前后端集成正确
2. **Mock 用于离线开发**：当后端不可用时临时使用
3. **保持 token 有效**：前端会自动刷新，但需要网络连接
4. **检查数据库**：确保有足够的测试数据