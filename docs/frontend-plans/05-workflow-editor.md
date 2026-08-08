# 05 · 工作流编辑器 Workflow Editor（Vue Flow）

> 原型页面：page-wf-editor。**重型核心模块**。视觉遵循参考站 Dify 风格（白顶栏 + 280px 节点面板 + 浅蓝节点卡 + 点阵画布）。
> 使用 `@vue-flow/core` + background + controls + minimap。

## 1. 目标

可视化编排画布：左侧拖拽节点 → 连线 → 配置 → 保存/发布 → 执行/单步调试（SSE 执行流染色）。

## 2. 页面布局（editor/EditorView.vue，BlankLayout 全屏）

```
┌─ EditorTopbar (56px 白) ─ 返回 | 流程名 | 状态 | 版本 | [撤销][重做][自动布局][保存][发布] ┐
├──────────────┬───────────────────────────────────────────────────────┤
│ NodePalette  │  VueFlow Canvas（dot 背景）                            │
│ 280px 白     │   节点卡(浅蓝#e6f7ff/描边#91d5ff) + 连线(带标签)        │
│ 分组节点     │   Controls(缩放) + MiniMap + DebugBar(调试态)           │
├──────────────┴───────────────────────────────────────────────────────┤
│ ExecutionPanel (底部日志面板，可折叠)                                  │
└──────────────────────────────────────────────────────────────────────┘
节点配置用 NodeConfigModal（浮层/抽屉，双击节点打开）
```

## 3. 12 种节点（原型 NODE_TYPES）

| 类型 | 中文 | 分组 | 色 |
|------|------|------|----|
| start | 开始 | basic | #334155 |
| end | 结束 | basic | #334155 |
| condition | 条件分支 | basic | #CA8A04 |
| loop | 循环 | basic | #0891B2 |
| human | 人工介入 | basic | #7C3AED |
| variable_assign | 变量赋值 | basic | #64748B |
| template_render | 模板渲染 | basic | #B45309 |
| llm | LLM 生成 | cap | #0369A1 |
| rag | RAG 检索 | cap | #0D9488 |
| code | 代码执行 | cap | #BE123C |
| http | HTTP 请求 | cap | #C2410C |
| tool | 外部工具 | cap | #9D174D |

## 4. 组件清单（views/workflow/editor/）

### 4.1 画布与节点

| 组件 | 路径 | 职责 |
|------|------|------|
| EditorView | editor/EditorView.vue | 容器：Topbar + 主体 + ExecutionPanel |
| WorkflowCanvas | canvas/WorkflowCanvas.vue | Vue Flow 容器：背景/控件/小地图；连线/拖入/删除/选中 |
| BaseNodeCard | canvas/nodes/BaseNodeCard.vue | 通用节点卡（图标 + 名 + 配置项预览行 + 状态点 + 耗时）；按 type 注入配色 |
| 节点特化卡 | canvas/nodes/{Start,End,Condition,Loop,Human,Variable,Template,LLM,RAG,Code,HTTP,Tool}NodeCard.vue | 各类型差异化内容（如 Condition 双出口、LLM 模型选择、RAG top_k） |
| TypedEdge | canvas/edges/TypedEdge.vue | 带标签连线（label + 端口 l/r）；运行态高亮流动 |
| NodePalette | canvas/panels/NodePalette.vue | 280px 左面板，按分组(basic/cap)列节点项，draggable |

### 4.2 配置浮层（editor/config/）

| 组件 | 职责 |
|------|------|
| NodeConfigModal | 配置容器（双击节点打开），按 type 切换下方表单 |
| LLMConfig / RAGConfig / CodeConfig / HTTPConfig | 各能力节点配置 |
| ConditionConfig | 条件表达式 + 双分支标签 |
| LoopConfig / HumanConfig(表单设计器) / VariableConfig / TemplateConfig(Jinja2) | 基础节点配置 |

### 4.3 执行/调试（editor/execution/）

| 组件 | 职责 |
|------|------|
| ExecutionPanel | 底部日志面板（可折叠/清空），日志计数 |
| ExecutionLog | 单条日志（时间 + 节点 + 级别 + 内容） |
| DebugToolbar | 调试态工具条：当前节点 + 继续/终止 |
| NodeOutputPopover | 节点输出摘要弹窗（点击节点查看输出） |

## 5. 数据模型（types/workflow.ts）

```ts
interface WfNode { id:string; type:NodeType; name:string; position:{x,y};
  data:{ rows:[string,string][]; config?:any } }
interface WfEdge { id:string; source:string; target:string; label?:string; sourceHandle?:'l'|'r' }
interface ExecState { [nodeId:string]: { status:'idle'|'running'|'success'|'error'|'wait'; durationMs?:number; output?:string } }
```

## 6. Store

### workflowEditorStore（编辑态）
```ts
state: { id, name, status:'draft'|'pub', version, dirty, nodes:[], edges:[], undoStack:[], selectedNodeId }
actions: {
  addNode(type, pos), updateNode(id), removeNode(id), addEdge(), removeEdge()
  save(), publish(), markDirty(), undo(), autoLayout()
  toDefinition() / fromDefinition(json)   // 与后端 def 互转
}
```
### workflowExecutionStore（执行态）
```ts
state: { executing, debugMode, execId, nodeStates:ExecState, logs:[] }
actions: {
  execute(debug:boolean)   // POST execute → 建 useSSE 订阅 /executions/{id}/stream
  cancel(), resume(), debugContinue(), testNode(nodeId)
}
```

## 7. SSE 执行流（设计文档 12.2.3）

```
execution_start(total_nodes) → node_start → node_progress → node_complete
→ (node_error/retry) → (human: execution_paused → resumed)
→ node_complete... → execution_complete | execution_error
```
按 node_id 更新 nodeStates 并给节点卡染色（running=#0284C7 描边 / success=绿 / error=红 / wait=紫），ExecutionPanel 追加日志。

## 8. 接口（设计文档 12.x）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/PUT/DELETE | /workflows/{id} | 详情/更新/删除 |
| POST | /workflows/{id}/publish | 发布 |
| POST | /workflows/{id}/execute | 执行 |
| GET | /executions/{id}/stream | SSE 执行状态 |
| POST | /executions/{id}/cancel /resume /debug/continue | 取消/续跑/调试 |
| POST | /executions/{id}/debug/test-node | 单节点 mock 测试 |
| GET | /executions/{id}/nodes/{nodeId} | 节点执行详情 |

## 9. Mock（mock/workflow.ts 补 editor 段）

- 节点 NODES + 连线 EDGES（原型数据），含 condition 双分支（cond_1 → tpl_1/var_1）。
- human 节点 → 执行时模拟 execution_paused。
- SSE 模拟器按拓扑顺序 emit 各节点 start/complete，LLM 节点模拟 retry。

## 10. Vue Flow 关键实现

- `useVueFlow()`：onConnect 建边、onNodeDragStop 落位、onNodeDoubleClick 开配置。
- 自定义节点：`template #node-{type}` 注册 12 个特化卡；BaseNodeCard 复用。
- 点阵背景 `<Background variant="dots">`；`<Controls>` 缩放；`<MiniMap>`。
- 自动布局：可选 dagre 计算位置。
- 选中删除：Delete 键 + 工具栏按钮；Ctrl+Z 撤销（undoStack）。

## 11. 实现步骤

1. 类型 + 两个 Store + Mock SSE。
2. EditorView 骨架 + Topbar（保存/发布/撤销）。
3. WorkflowCanvas + 12 节点卡 + TypedEdge + 拖入连线。
4. NodePalette（拖拽源）+ Controls/MiniMap/Background。
5. NodeConfigModal + 各 Config 表单。
6. ExecutionPanel + 执行 SSE 染色。
7. DebugToolbar（单步）+ NodeOutputPopover。

## 12. 验收

- [ ] 从面板拖节点入画布、连线、双击配置、删除、撤销。
- [ ] 保存/发布；状态/版本/脏标正确。
- [ ] 执行：节点按序染色，日志实时滚动；human 节点暂停等待。
- [ ] 单步调试：逐节点继续/终止。
- [ ] 缩放/小地图/自动布局可用。