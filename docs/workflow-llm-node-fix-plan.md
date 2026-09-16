# 工作流 LLM 节点问题修复方案

## 📋 问题总结

### 问题 1：工作流执行是纯前端模拟
- **位置**：`frontend/src/views/workflow/WorkflowEditorView.vue` 第 302-349 行
- **影响**：没有调用真实后端 API，所有节点输出都是模拟数据

### 问题 2：变量引用语法不一致
- **前端**：`${node_id.output}`（useWorkflowParams.ts 第 74、88 行）
- **后端**：`{{node_id.output}}`（backend/app/core/engine/state.py 第 26 行）

### 问题 3：LLM 节点配置界面不完整
- **缺失**：用户提示词（user_prompt）配置输入框
- **命名不一致**：`systemPrompt`（前端）vs `system_prompt`（后端）

### 问题 4：输入变量映射机制未被使用
- **前端**：提供了输入变量映射功能
- **后端**：LLMExecutor 没有使用映射后的变量

---

## 🔧 解决方案

### 步骤 1：修复前端变量引用语法

**文件**：`frontend/src/composables/useWorkflowParams.ts`

**修改第 74、88 行**：
```typescript
// 修改前
path: `\${${node.id}.${p.name}}`

// 修改后
path: `{{${node.id}.${p.name}}}`
```

---

### 步骤 2：增强 LLM 节点配置界面

**文件**：`frontend/src/views/workflow/components/NodeConfigModal.vue`

**在第 341 行后添加用户提示词配置**：
```vue
<el-form-item label="系统提示">
  <el-input v-model="form.config.systemPrompt" type="textarea" :rows="3" placeholder="系统提示词" />
</el-form-item>

<!-- 新增：用户提示词配置 -->
<el-form-item label="用户提示">
  <el-input
    v-model="form.config.userPrompt"
    type="textarea"
    :rows="3"
    placeholder="用户提示词，可引用上游变量，如：{{start.query}}"
  />
  <div style="color: #909399; font-size: 12px; margin-top: 4px;">
    使用 {{节点ID.变量名}} 引用上游节点输出，如 {{start.query}}
  </div>
</el-form-item>

<el-form-item label="温度">
  ...
</el-form-item>
```

---

### 步骤 3：修改后端 LLM 执行器配置字段映射

**文件**：`backend/app/core/engine/nodes/basic.py`

**修改第 34-35 行**：
```python
# 修改前
sys_prompt = resolve(self.config.get("system_prompt", ""), state)
usr_prompt = resolve(self.config.get("user_prompt", ""), state)

# 修改后（兼容两种命名方式）
sys_prompt = resolve(self.config.get("system_prompt") or self.config.get("systemPrompt", ""), state)
usr_prompt = resolve(self.config.get("user_prompt") or self.config.get("userPrompt", ""), state)
```

---

### 步骤 4：实现真实后端 API 调用（推荐方案）

#### 方案 A：修改前端直接调用后端 API

**文件**：`frontend/src/views/workflow/WorkflowEditorView.vue`

**修改第 199-243 行的 `doExecute` 函数**：
```typescript
async function doExecute(debug: boolean, inputs: Record<string, any>) {
  executing.value = true
  debugAbort.value = false
  execStore.reset()
  execStore.debugMode = debug

  try {
    // 方案 1：调用后端 API 执行整个工作流
    const response = await wfApi.executeWorkflow(store.id, {
      debug,
      inputs
    })

    // 监听 SSE 事件流
    const eventSource = new EventSource(`/api/v2/workflows/executions/${response.executionId}/stream`)

    eventSource.addEventListener('node_start', (event) => {
      const data = JSON.parse(event.data)
      execStore.updateNodeState(data.node_id, { status: 'running' })
      execStore.addLog(data.node_id, 'info', '开始执行节点: ' + data.node_name)
    })

    eventSource.addEventListener('node_complete', (event) => {
      const data = JSON.parse(event.data)
      execStore.updateNodeState(data.node_id, {
        status: data.status,
        output: data.output
      })
      execStore.addLog(data.node_id, data.status, '节点执行完成')
    })

    eventSource.addEventListener('execution_complete', (event) => {
      const data = JSON.parse(event.data)
      eventSource.close()
      executing.value = false
      if (data.success) {
        ElMessage.success('执行完成')
      } else {
        ElMessage.error('执行失败')
      }
    })

    eventSource.addEventListener('error', (error) => {
      console.error('SSE error:', error)
      eventSource.close()
      executing.value = false
      ElMessage.error('执行失败')
    })

  } catch (error) {
    ElMessage.error('执行失败')
  } finally {
    executing.value = false
  }
}
```

#### 方案 B：保留前端模拟，但调用真实 LLM API

**文件**：`frontend/src/views/workflow/WorkflowEditorView.vue`

**修改第 336-345 行**：
```typescript
// 模拟 LLM 节点 → 改为调用真实 LLM API
if (node.type === 'llm') {
  try {
    // 构建请求
    const config = node.data?.config || {}
    const systemPrompt = config.systemPrompt || 'You are a helpful assistant.'
    const userPrompt = config.userPrompt || ''

    // 解析变量引用（简化版）
    const resolvedUserPrompt = userPrompt.replace(/\{\{(\w+)\.(\w+)\}\}/g, (match, nodeId, varName) => {
      // 从上游节点输出中查找变量
      const upstreamOutput = execStore.getNodeOutput(nodeId)
      return upstreamOutput?.[varName] || match
    })

    // 调用后端 LLM API
    const response = await fetch('/api/v2/llm/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authStore.token}`
      },
      body: JSON.stringify({
        model: config.model,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: resolvedUserPrompt || inputs?.query || 'Hello!' }
        ],
        temperature: config.temperature || 0.7,
        max_tokens: config.maxTokens || 2000
      })
    })

    const data = await response.json()

    if (data.code === 0) {
      const output = {
        result: '分析完成',
        content: data.data.content,
        tokens: data.data.usage
      }
      execStore.updateNodeState(node.id, { status: 'success', output: JSON.stringify(output) })
      execStore.addLog(node.id, 'result', 'LLM 输出: ' + output.content.slice(0, 100) + '...')
      return output
    } else {
      throw new Error(data.message || 'LLM 调用失败')
    }
  } catch (error) {
    execStore.updateNodeState(node.id, { status: 'error' })
    execStore.addLog(node.id, 'error', 'LLM 调用失败: ' + error.message)
    throw error
  }
}
```

---

## 📝 使用示例

### 配置示例

1. **开始节点**：定义输入参数 `query`
2. **LLM 节点**：
   - 系统提示：`你是一个有帮助的助手。`
   - 用户提示：`{{start.query}}`（引用开始节点的输入）
3. **结束节点**：输出 `{{llm_1.content}}`

### 执行流程

```
开始(query="你是谁") → LLM(userPrompt="{{start.query}}") → 结束
```

**实际调用**：
```json
{
  "model": "gpt-4",
  "messages": [
    {"role": "system", "content": "你是一个有帮助的助手。"},
    {"role": "user", "content": "你是谁"}
  ]
}
```

---

## ⚠️ 注意事项

1. **变量引用语法**：统一使用 `{{node_id.variable}}` 格式
2. **字段命名**：前端使用驼峰（systemPrompt），后端兼容驼峰和下划线
3. **安全性**：确保 API 调用携带认证 Token
4. **错误处理**：妥善处理网络错误和 API 错误

---

## 🎯 推荐实施顺序

1. ✅ **步骤 1**：修复变量引用语法（最小改动）
2. ✅ **步骤 2**：增强 LLM 节点配置界面
3. ✅ **步骤 3**：修改后端字段映射兼容性
4. ⏳ **步骤 4**：选择方案 A（推荐）或方案 B 实现真实 API 调用

---

## 📚 相关文件清单

### 需要修改的文件
1. `frontend/src/composables/useWorkflowParams.ts` - 变量引用语法
2. `frontend/src/views/workflow/components/NodeConfigModal.vue` - LLM 配置界面
3. `backend/app/core/engine/nodes/basic.py` - 后端字段映射
4. `frontend/src/views/workflow/WorkflowEditorView.vue` - 工作流执行逻辑

### 相关参考文件
- `backend/app/core/engine/state.py` - 变量解析器
- `backend/app/core/engine/graph_builder.py` - 工作流引擎
- `frontend/src/stores/workflow.ts` - 工作流状态管理

---

## ✅ 验证清单

- [ ] 变量引用语法前后端一致
- [ ] LLM 节点配置界面包含用户提示词
- [ ] 后端能正确解析前端配置
- [ ] 工作流执行调用真实 API
- [ ] 变量引用能正确传递和解析
- [ ] 错误处理完善