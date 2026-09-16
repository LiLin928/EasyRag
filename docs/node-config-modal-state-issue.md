# NodeConfigModal 状态混乱问题分析

## 问题现象
1. LLM 节点不能添加输入变量
2. 点击 LLM 节点后，再点击其他节点，都显示 LLM 的配置

## 根本原因

### 问题代码（第 48-62 行）
```typescript
watch(
  () => props.node,
  (node) => {
    if (node) {
      form.value.name = node.name
      const cfg = node.data?.config || {}
      form.value.config = { ...cfg }  // ❌ 浅拷贝，不会清除旧值！
      form.value.inputVariables = (cfg.input_variables ? [...cfg.input_variables] : [])
        .map((v: any) => ({ ...v }))
      form.value.outputVariables = (cfg.output_variables ? [...cfg.output_variables] : [])
        .map((v: any) => ({ ...v }))
    }
  },
  { immediate: true }
)
```

### 问题分析

1. **浅拷贝问题**：
   - `form.value.config = { ...cfg }` 是浅拷贝
   - 如果新节点缺少某些字段，`{ ...cfg }` 不会覆盖这些字段
   - 导致 `form.value.config` 保留了上一个节点的配置

2. **示例场景**：
   ```
   1. 用户打开 LLM 节点，配置了：
      - systemPrompt: "你是一个助手"
      - userPrompt: "{{start.query}}"
      - temperature: 0.7

   2. 用户切换到 RAG 节点，RAG 节点原始配置：
      - kbIds: []
      - topK: 5

   3. 执行 form.value.config = { ...cfg } 后：
      form.value.config = {
        systemPrompt: "你是一个助手",  // ❌ 来自 LLM 节点！
        userPrompt: "{{start.query}}",  // ❌ 来自 LLM 节点！
        temperature: 0.7,                // ❌ 来自 LLM 节点！
        kbIds: [],
        topK: 5
      }
   ```

## 解决方案

### 方案 1：完全重置 form 状态
```typescript
watch(
  () => props.node,
  (node) => {
    if (node) {
      // ✅ 先完全重置 form
      form.value = {
        name: '',
        config: {},
        inputVariables: [],
        outputVariables: []
      }

      // ✅ 然后赋值新节点的配置
      form.value.name = node.name
      const cfg = node.data?.config || {}
      form.value.config = { ...cfg }
      form.value.inputVariables = (cfg.input_variables ? [...cfg.input_variables] : [])
        .map((v: any) => ({ ...v }))
      form.value.outputVariables = (cfg.output_variables ? [...cfg.output_variables] : [])
        .map((v: any) => ({ ...v }))
    }
  },
  { immediate: true }
)
```

### 方案 2：使用深拷贝
```typescript
import { cloneDeep } from 'lodash-es'

watch(
  () => props.node,
  (node) => {
    if (node) {
      form.value.name = node.name
      const cfg = node.data?.config || {}
      form.value.config = cloneDeep(cfg)  // ✅ 深拷贝
      form.value.inputVariables = cloneDeep(cfg.input_variables || [])
      form.value.outputVariables = cloneDeep(cfg.output_variables || [])
    }
  },
  { immediate: true }
)
```

## 推荐方案

**方案 1**（完全重置）更简单可靠，推荐使用。

## 其他发现

### 输入变量映射问题
检查 `showInputMapping` 计算属性：
```typescript
const showInputMapping = computed(() => !isStartNode.value && !isEndNode.value)
```

LLM 节点应该显示输入变量映射，但可能因为状态混乱导致显示异常。