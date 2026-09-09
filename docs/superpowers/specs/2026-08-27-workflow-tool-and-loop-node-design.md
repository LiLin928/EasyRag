# 工作流工具节点增强与循环节点设计 — 设计文档

> 日期：2026-08-27
> 模块：05 工作流编辑器
> 状态：已批准，实施中

---

## 一、背景

工作流编辑器存在两个待完善功能：

1. **外部工具节点**：当前配置为手动输入工具 ID 和参数文本，应改为从系统工具管理模块选择已配置的工具。
2. **循环节点**：已有 `loop` 节点类型但无配置区域，需要设计循环逻辑。

---

## 二、工具节点增强

### 2.1 修改方案

| # | 文件 | 修改 |
|---|------|------|
| 1 | `NodeConfigModal.vue` | 引入 `useToolStore`，`onMounted` 调用 `loadTools()` |
| 2 | `NodeConfigModal.vue` | 工具 ID 的 `el-input` → `el-select`，选项来自 `toolStore.tools`（仅 `enabled: true`） |
| 3 | `NodeConfigModal.vue` | 选中工具后，根据 `ToolParam[]` 动态渲染参数表单 |
| 4 | `NodeConfigModal.vue` | 参数值存入 `form.config.params` 对象（`{ paramName: value }`） |
| 5 | `NodeConfigModal.vue` | `buildPreviewRows()` 增加 `['工具', selectedTool?.name]` |

### 2.2 动态参数渲染规则

根据 `ToolParam.t`（类型）生成对应输入控件：

| ToolParam.t | 控件 |
|-------------|------|
| `string` | `el-input` |
| `number` | `el-input-number` |
| `boolean` | `el-switch` |
| `object` / `array` | `el-input` textarea |

---

## 三、循环节点设计：循环开始 + 循环结束（双节点配对）

### 3.1 设计决策

单节点方案存在缺陷：无法界定循环体边界。采用**双节点配对**方案：

- **循环开始**（`loop`）：配置迭代参数，输出 `item`/`index`
- **循环结束**（`loop_end`，新增）：标记循环体终点，收集结果，输出 `result`

### 3.2 流程示意

```
[开始] → [循环开始] ──item/index──→ [节点A] → [节点B] → [循环结束] ──result──→ [结束]
               ↑───── 循环体 ─────↑           ↑──循环后──↑
```

### 3.3 循环开始节点配置

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `loop_mode` | `el-select` | `foreach`（遍历数组）/ `count`（指定次数）/ `while`（条件循环） |
| `loop_variable` | `el-select`（选上游变量） | foreach 模式：要遍历的数组（如 `${rag_1.documents}`） |
| `max_iterations` | `el-input-number` | count 模式循环次数；所有模式的安全上限 |
| `condition_expr` | `el-input` | while 模式条件（如 `index < 10`） |

输出变量：`item`（当前元素）、`index`（当前索引）

### 3.4 循环结束节点配置

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `collect_variable` | `el-select`（选上游变量） | 要收集的变量（如 `${节点B.output}`） |
| `collect_mode` | `el-select` | `array`（每轮结果聚合成数组）/ `last`（取最后一轮的值） |

输出变量：`result`（聚合结果）

### 3.5 执行引擎逻辑

1. 到达"循环开始"节点，读取迭代配置
2. 对每次迭代：执行从"循环开始"到"循环结束"之间路径上的所有节点
3. 每轮结束时，"循环结束"节点收集 `collect_variable` 的值
4. 所有迭代完成后，"循环结束"输出聚合的 `result`，继续执行下游节点

### 3.6 多分支循环体

```
[循环开始] → [条件判断] ──yes──→ [节点B] → [循环结束]
                 │
                 └──no──→ [节点C] → [循环结束]
```

---

## 四、涉及文件清单

| # | 文件 | 操作 | 说明 |
|---|------|------|------|
| 1 | `frontend/src/types/workflow.ts` | 修改 | 新增 `loop_end` 到 `NodeType`/`NODE_TYPES`/`NODE_OUTPUT_PARAMS` |
| 2 | `frontend/src/views/workflow/components/BaseNodeCard.vue` | 修改 | 新增 `loop_end` 颜色/图标 |
| 3 | `frontend/src/views/workflow/components/NodeConfigModal.vue` | 修改 | 工具节点改选择 + 循环开始/结束配置 |

---

## 五、约束

- 遵循 `frontend/AGENTS.md`：Vue 3 `<script setup lang="ts">`、Element Plus、Pinia、`@vue-flow/core`
- 禁止引入新依赖
- 禁止修改 `frontend-prototype/`
- UI 组件只用 Element Plus
- `npm run build` 必须零错误
