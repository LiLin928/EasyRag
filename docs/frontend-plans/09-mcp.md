# 09 · MCP 服务 MCP

> 原型页面：page-mcp。管理 Model Context Protocol 服务（stdio/SSE）：环境变量、超时、连通测试。

## 1. 目标

卡片/列表展示 MCP 服务；配置弹窗含类型/命令/环境变量/超时；启用/停用；连通测试（检测工具数）。

## 2. 组件清单（views/mcp/）

| 组件 | 路径 | 职责 |
|------|------|------|
| McpView | McpView.vue | 容器 + 「添加 MCP」+ 列表/卡片 |
| McpCard | components/McpCard.vue | 卡片：类型徽标(stdio/SSE) + 名称 + 命令(monospace) + 状态(运行中/停止/错误) + 工具数；操作（配置/测试/启停/删除） |
| McpConfigDialog | components/McpConfigDialog.vue | el-dialog：名称/类型(stdio|SSE)/命令或 URL/超时(秒)/环境变量表(动态行 key/value，支持显示/隐藏敏感值) |
| McpTestResult | components/McpTestResult.vue | 测试结果：连通状态 + 暴露的工具数与列表 |

## 3. 数据模型（types/mcp.ts）
```ts
interface Mcp { id:string; name:string; tp:'stdio'|'SSE'; cmd:string;
  status:'on'|'off'|'err'; toolCount:number; env:{k:string;v:string}[]; timeout:number }
```

## 4. Store（stores/mcp.ts）：CRUD + toggle + testMcp(id)（Mock 返回工具数，可模拟 err）。

## 5. Mock（mock/mcp.ts）：原型 MCPS（filesystem/github/postgres/brave-search，含 stdio/SSE/错误态）。

## 6. 实现步骤
1. 类型 + Store + Mock。2. 卡片列表 + 启停。3. 配置弹窗（类型切换 + 环境变量动态行 + 敏感值掩码）。4. 连通测试。

## 7. 验收
- [ ] 添加/编辑/删除/启停 MCP；stdio/SSE 类型切换。
- [ ] 环境变量动态增删，敏感值默认掩码、可临时显示。
- [ ] 测试返回工具数；错误态正确展示。