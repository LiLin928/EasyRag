# 06 · 智能体 Agents

> 原型页面：page-agents。装配自定义工具/知识库/工作流/MCP/技能，组合成可对话的专属助手。

## 1. 目标

卡片网格展示智能体；卡片进入配置抽屉（模型/Prompt/温度/挂载的工具·文档·工作流·MCP·技能）；可开/关；可发起对话。

## 2. 组件清单（views/agents/）

| 组件 | 路径 | 职责 |
|------|------|------|
| AgentsView | AgentsView.vue | 容器 + 「新建智能体」+ 卡片网格 |
| AgentCard | components/AgentCard.vue | 卡片：名称 + 描述 + 模型 + 已挂载能力徽标 + 开关 + 最近活跃；操作（配置/对话/删除） |
| AgentConfigDrawer | components/AgentConfigDrawer.ts | el-drawer 配置抽屉：基础信息 + 模型/温度/MaxTokens + 系统提示词 |
| AgentCapabilityPicker | components/AgentCapabilityPicker.vue | 多选挂载：工具(07)/文档(03)/工作流(04)/MCP(09)/技能(08)，分 Tab 勾选 |
| AgentChatDrawer | components/AgentChatDrawer.ts | 抽屉式对话（复用 02 的流式渲染，限定该智能体上下文） |

## 3. 数据模型（types/agent.ts）

```ts
interface Agent {
  id:string; name:string; desc:string; model:string; prompt:string;
  temp:number; maxtok:string;
  tools:string[]; docs:string[]; wfs:string[]; mcps:string[]; skills:string[];
  enabled:boolean; lastActive:string;
}
```

## 4. Store（stores/agent.ts）
```ts
state:{ agents:Agent[] }
actions:{ loadAgents(), createAgent(), updateAgent(id), deleteAgent(id), toggleAgent(id) }
```

## 5. 接口：GET/POST/PUT/DELETE /agents[/:id]（前端先行 mock）。
挂载项的候选来自 tools/docs/workflows/mcps/skills 各自 Store。

## 6. Mock（mock/agent.ts）：原型 AGENTS（客服小智/研报分析师/运维巡检员，含各能力挂载与启停）。

## 7. 实现步骤
1. 类型 + Store + Mock。2. 卡片网格 + 开关。3. 配置抽屉 + 能力多选。4. 对话抽屉（复用流式）。

## 8. 验收
- [ ] 新建/编辑/删除/启停智能体。
- [ ] 能多选挂载工具/文档/工作流/MCP/技能。
- [ ] 卡片发起对话能流式回答。