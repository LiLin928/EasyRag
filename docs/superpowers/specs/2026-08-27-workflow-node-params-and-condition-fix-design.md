# 工作流节点参数传递与条件节点连线修复 — 设计文档

> 日期：2026-08-27
> 模块：05 工作流编辑器
> 状态：已批准，待实施

---

## 一、背景与目标

EasyRAG 工作流编辑器存在两个问题：

1. **条件节点连线 bug**：条件节点的两条输出线从节点底部出来，而非从右侧的 "是/否" 出口点出来。
2. **缺乏自定义参数与节点间参数传递**：当前节点配置仅有基础字段（模型/温度/TopK 等），没有输入变量引用上游节点输出、输出变量定义等机制。

目标：修复条件节点连线 bug，并参考 MyRAG01 项目设计，为 EasyRAG 添加节点间参数传递能力。

---

## 二、问题一：条件节点连线 Bug

### 2.1 根因

Vue Flow 通过 `edge.sourceHandle` 查找同 `id` 的 Handle。当前存在 **ID 不匹配**：

| 位置 | 代码 | 实际值 |
|------|------|--------|
| `BaseNodeCard.vue` Handle 定义 | `id="yes"` / `id="no"` | `'yes'` / `'no'` |
| `mock/workflow.ts` 边数据 | `sourceHandle: 'r'` / `sourceHandle: 'l'` | `'r'` / `'l'` |
| `types/workflow.ts` 类型 | `sourceHandle?: 'l' \| 'r'` | 只允许 `'l'`/`'r'` |

Vue Flow 找不到 id 为 `'r'`/`'l'` 的 Handle → 回退到默认位置（节点底部）。

### 2.2 其他节点检查

- start/llm/rag/code/http 等节点只有**单个** source Handle，**无显式 id** → Vue Flow 用默认匹配（`sourceHandle: null` 即可匹配），不受影响。
- `BaseNodeCard.vue` 中条件节点的 Handle 定义本身**正确**（两个右侧出口，30%/70% 位置），不需要改动。

### 2.3 修复方案（3 个文件）

| # | 文件 | 修改 |
|---|------|------|
| 1 | `frontend/src/types/workflow.ts` | `WfEdge.sourceHandle` 类型改为 `'yes' \| 'no' \| undefined` |
| 2 | `frontend/src/mock/workflow.ts` | `sourceHandle: 'r'` → `'yes'`，`sourceHandle: 'l'` → `'no'` |
| 3 | `frontend/src/views/workflow/components/WorkflowCanvas.vue` | `onConnect` 类型断言改为 `'yes' \| 'no' \| undefined` |

---

## 三、问题二：自定义参数与节点间参数传递

### 3.1 参考项目设计（MyRAG01）

MyRAG01 的 `NodeConfigPanel.tsx` 实现了完整的参数传递：

- **`InputVariableMapping`**：引用上游节点输出，`source` 字段为路径如 `${node_id.result}`
- **`OutputVariableMapping`**：声明本节点产出变量
- **`getUpstreamNodes()`**：通过边关系找到前置节点
- **`getNodeOutputParams()`**：按节点类型返回输出参数列表（如 LLM → `result` + `content`）
- 配置面板中输入参数的 `source` 为下拉框，选项来自上游节点输出

### 3.2 EasyRAG 方案

#### 3.2.1 类型扩展（`types/workflow.ts`）

新增以下类型：

```ts
// 输入变量映射 — 引用上游节点输出
export interface InputVariableMapping {
  name: string       // 参数名，如 "query"
  label?: string     // 显示名
  source?: string    // 引用路径，如 "${llm_1.result}"
  default?: any      // 默认值
}

// 输出变量定义 — 声明本节点产出
export interface OutputVariableMapping {
  name: string       // 变量名，如 "result"
  path?: string      // JSON 提取路径，如 "content"
}

// 每种节点类型的默认输出参数
export const NODE_OUTPUT_PARAMS: Record<NodeType, OutputVariableMapping[]>
```

#### 3.2.2 新建 composable（`composables/useWorkflowParams.ts`）

```ts
// 获取上游节点（通过边关系）
export function getUpstreamNodes(nodeId, nodes, edges): WfNode[]

// 获取节点的输出参数列表（展示名 + 引用路径）
export function getNodeOutputParams(node: WfNode): { name: string; path: string }[]

// 构建上游所有可引用变量列表（用于下拉选择）
export function getUpstreamOutputOptions(nodeId, nodes, edges): { name: string; path: string }[]
```

#### 3.2.3 增强 `NodeConfigModal.vue`

在现有配置表单下方追加：

- **输入变量映射区**：每行一个输入参数，`source` 字段为 `el-select` 下拉，选项来自上游节点输出
- **输出变量定义区**（可选）：让用户定义本节点产出变量名

不破坏现有配置字段，追加而非替换。

#### 3.2.4 mock 数据补充

`mock/workflow.ts` 的 mockNodes 补充 `config.input_variables` 示例数据，使演示效果完整。

---

## 四、涉及文件清单

| # | 文件 | 操作 | 说明 |
|---|------|------|------|
| 1 | `frontend/src/types/workflow.ts` | 修改 | 修复 sourceHandle 类型 + 新增参数类型 |
| 2 | `frontend/src/mock/workflow.ts` | 修改 | 修复 sourceHandle 值 + 补充参数示例 |
| 3 | `frontend/src/views/workflow/components/WorkflowCanvas.vue` | 修改 | 修复 onConnect 类型断言 |
| 4 | `frontend/src/composables/useWorkflowParams.ts` | 新建 | 上游节点计算 + 输出参数获取 |
| 5 | `frontend/src/views/workflow/components/NodeConfigModal.vue` | 修改 | 增加输入/输出变量 UI |

---

## 五、实施顺序

1. 修复条件节点连线 bug（文件 1-3）
2. 新增参数类型定义（文件 1）
3. 新建 composable（文件 4）
4. 增强 NodeConfigModal（文件 5）
5. 补充 mock 数据（文件 2）
6. `npm run build` 验证零错误

---

## 六、约束

- 遵循 `frontend/AGENTS.md`：Vue 3 `<script setup lang="ts">`、Element Plus、Pinia、`@vue-flow/core`
- 禁止引入新依赖
- 禁止修改 `frontend-prototype/`
- UI 组件只用 Element Plus
- 类型集中在 `types/` 目录
