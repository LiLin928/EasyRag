<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch, computed, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useWorkflowEditorStore, useWorkflowExecutionStore } from '@/stores/workflow'
import { useAuthStore } from '@/stores/auth'
import * as wfApi from '@/api/workflow'
import WorkflowCanvas from './components/WorkflowCanvas.vue'
import NodeConfigModal from './components/NodeConfigModal.vue'
import ExecutionPanel from './components/ExecutionPanel.vue'
import DebugToolbar from './components/DebugToolbar.vue'
import type { WfNode } from '@/types/workflow'
import { NODE_TYPES } from '@/types/workflow'

const route = useRoute()
const router = useRouter()
const store = useWorkflowEditorStore()
const execStore = useWorkflowExecutionStore()

const saving = ref(false)
const publishing = ref(false)
const executing = ref(false)
const configVisible = ref(false)
const selectedNode = ref<WfNode | null>(null)

// 调试控制
const debugPaused = ref(false)
const debugAbort = ref(false)
const debugCurrentIndex = ref(0)

// 开始节点输入参数弹窗
const startInputVisible = ref(false)
const startInputValues = ref<Record<string, any>>({})
const startInputVariables = ref<StartInputVariable[]>([])
const pendingDebug = ref(false)

// 扩展输入变量定义，包含 required 属性
interface StartInputVariable {
  name: string
  label?: string
  source?: string
  default?: any
  required?: boolean
  type?: string
}

const basicNodes = NODE_TYPES.filter(n => n.group === 'basic')

const capNodes = NODE_TYPES.filter(n => n.group === 'cap')

// 获取开始节点的输入变量定义
const startNode = computed(() => {
  return store.nodes.find(n => n.type === 'start')
})

const hasStartInputVariables = computed(() => {
  const start = startNode.value
  if (!start) return false
  const inputVars = start.data?.config?.input_variables as StartInputVariable[]
  return inputVars && inputVars.length > 0
})

onMounted(async () => {
  const id = route.params.id as string
  if (id === 'new') {
    store.id = ''
    store.name = '新流程'
    store.status = 'draft'
    store.version = 1
    store.nodes = []
    store.edges = []
  } else {
    try {
      await store.load(id)
    } catch (error) {
      ElMessage.error('加载失败')
      router.push('/workflows')
    }
  }

  // 添加页面关闭提示
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
})

function handleBeforeUnload(e: BeforeUnloadEvent) {
  if (store.dirty) {
    e.preventDefault()
    e.returnValue = '工作流尚未保存，确定要离开吗？'
    return e.returnValue
  }
}

async function handleBack() {
  // 如果有未保存的修改，提示用户
  if (store.dirty) {
    try {
      await ElMessageBox.confirm(
        '工作流尚未保存，是否保存？',
        '提示',
        {
          confirmButtonText: '保存',
          cancelButtonText: '不保存',
          type: 'warning'
        }
      )
      // 用户选择保存
      await store.save()
      ElMessage.success('保存成功')
    } catch (action) {
      // 用户选择不保存或关闭弹窗
      if (action !== 'cancel') {
        return  // 用户关闭了弹窗，不离开页面
      }
    }
  }
  router.push('/workflows')
}

async function handleSave() {
  // 如果是新工作流，先创建
  if (!store.id) {
    try {
      const wf = await store.create()
      router.replace('/workflows/editor/' + wf.id)
      ElMessage.success('创建成功')
    } catch (error) {
      ElMessage.error('创建失败')
    }
    return
  }

  // 更新已存在的工作流
  saving.value = true
  try {
    await store.save()
    ElMessage.success('保存成功')
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handlePublish() {
  // 如果是新工作流，先创建并保存
  if (!store.id) {
    try {
      const wf = await store.create()
      router.replace('/workflows/editor/' + wf.id)
      // 创建成功后继续发布
    } catch (error) {
      ElMessage.error('创建失败')
      return
    }
  }

  publishing.value = true
  try {
    await store.publish()
    ElMessage.success('发布成功')
  } catch (error) {
    ElMessage.error('发布失败')
  } finally {
    publishing.value = false
  }
}

function handleUndo() {
  store.undo()
}

function handleAutoLayout() {
  const nodeWidth = 200
  const gap = 50
  
  const sortedNodes = [...store.nodes].sort((a, b) => {
    const order: Record<string, number> = { start: 0, end: 100 }
    return (order[a.type] || 50) - (order[b.type] || 50)
  })
  
  sortedNodes.forEach((node, i) => {
    store.updateNode(node.id, {
      position: { x: 100 + (i * (nodeWidth + gap)), y: 100 }
    })
  })
  
  ElMessage.success('自动布局完成')
  store.markDirty()
}

// 检查并显示开始节点输入弹窗
async function handleExecute(debug: boolean) {
  // 如果是新工作流，先创建并保存
  if (!store.id) {
    try {
      const wf = await store.create()
      router.replace('/workflows/editor/' + wf.id)
      // 创建成功后继续执行
    } catch (error) {
      ElMessage.error('创建失败')
      return
    }
  }
  
  // 如果有开始节点输入参数，显示弹窗
  if (hasStartInputVariables.value) {
    pendingDebug.value = debug
    const start = startNode.value!
    const inputVars = start.data?.config?.input_variables as StartInputVariable[]
    startInputVariables.value = inputVars
    
    // 初始化输入值（使用默认值）
    const initialValues: Record<string, any> = {}
    inputVars.forEach(v => {
      initialValues[v.name] = v.default !== undefined ? v.default : ''
    })
    startInputValues.value = initialValues
    startInputVisible.value = true
    return
  }
  
  // 没有输入参数，直接执行
  await doExecute(debug, {})
}

// 确认开始节点输入后执行
async function confirmStartInput() {
  startInputVisible.value = false
  await doExecute(pendingDebug.value, startInputValues.value)
}

// 实际执行流程（调用真实后端 API）
async function doExecute(debug: boolean, inputs: Record<string, any>) {
  executing.value = true
  debugAbort.value = false
  execStore.reset()
  execStore.debugMode = debug
  debugCurrentIndex.value = 0

  try {
    // 调用后端 API 执行工作流
    const response = await wfApi.executeWorkflow(store.id, debug, inputs)
    const executionId = response.executionId

    // 保存当前执行 ID
    execStore.execId = executionId

    // 使用 Fetch API 连接 SSE（支持 Authorization）
    const streamUrl = wfApi.getExecutionStreamUrl(executionId)
    const authStore = useAuthStore()

    const sseResponse = await fetch(streamUrl, {
      headers: {
        'Authorization': `Bearer ${authStore.token}`,
        'Accept': 'text/event-stream',
      },
    })

    if (!sseResponse.ok) {
      throw new Error(`SSE connection failed: ${sseResponse.status}`)
    }

    const reader = sseResponse.body?.getReader()
    if (!reader) {
      throw new Error('No response body')
    }

    const decoder = new TextDecoder()
    let buffer = ''

    // 读取 SSE 流
    const readStream = async () => {
      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })

          // 解析 SSE 事件
          const events = buffer.split('\n\n')
          buffer = events.pop() || ''

          for (const eventStr of events) {
            if (!eventStr.trim()) continue

            const lines = eventStr.split('\n')
            let eventType = 'message'
            let data = ''

            for (const line of lines) {
              if (line.startsWith('event:')) {
                eventType = line.substring(6).trim()
              } else if (line.startsWith('data:')) {
                data = line.substring(5).trim()
              }
            }

            // 处理事件
            if (data) {
              try {
                const parsedData = JSON.parse(data)
                handleSSEEvent(eventType, parsedData)
              } catch (e) {
                console.error('Failed to parse SSE data:', e)
              }
            }
          }
        }
      } catch (error) {
        console.error('SSE stream error:', error)
      }
    }

    readStream() // 开始读取流

  } catch (error: any) {
    console.error('Execute workflow error:', error)
    ElMessage.error('执行失败: ' + (error.response?.data?.message || error.message))
  } finally {
    executing.value = false
    execStore.executing = false
  }
}

// 处理 SSE 事件
function handleSSEEvent(eventType: string, data: any) {
  switch (eventType) {
    case 'execution_start':
      execStore.addLog('workflow', 'info', `开始执行工作流，共 ${data.total_nodes} 个节点`)
      break

    case 'node_start':
      execStore.updateNodeState(data.node_id, { status: 'running' })
      execStore.addLog(data.node_id, 'info', '开始执行节点: ' + data.node_name)
      break

    case 'node_progress':
      if (data.message) {
        execStore.addLog(data.node_id, 'info', data.message)
      }
      break

    case 'node_complete':
      execStore.updateNodeState(data.node_id, {
        status: data.status,
        output: data.output,
        durationMs: data.duration_ms
      })
      if (data.output) {
        execStore.addLog(data.node_id, 'result', '输出: ' + data.output.slice(0, 100) + '...')
      }
      execStore.addLog(data.node_id, data.status, '节点执行完成')
      break

    case 'node_error':
      execStore.updateNodeState(data.node_id, { status: 'error' })
      execStore.addLog(data.node_id, 'error', '执行错误: ' + data.error)
      if (data.retry_count) {
        execStore.addLog(data.node_id, 'warning', `重试 ${data.retry_count} 次`)
      }
      break

    case 'execution_paused':
      execStore.updateNodeState(data.node_id, { status: 'wait' })
      execStore.addLog(data.node_id, 'warning', `工作流暂停，原因: ${data.reason}`)
      debugPaused.value = true
      break

    case 'execution_resumed':
      execStore.addLog(data.node_id, 'info', '工作流已恢复')
      debugPaused.value = false
      break

    case 'execution_complete':
      executing.value = false
      execStore.executing = false
      debugPaused.value = false
      if (data.success) {
        ElMessage.success(`执行完成，总耗时 ${data.total_duration_ms}ms`)
      } else {
        ElMessage.error('执行失败')
      }
      break

    case 'execution_error':
      executing.value = false
      execStore.executing = false
      ElMessage.error('执行错误: ' + data.error)
      break
  }
}

// 调试控制
async function handleDebugContinue() {
  // 继续执行：调用后端 API resume
  if (execStore.execId) {
    try {
      await wfApi.debugContinue(execStore.execId)
    } catch (error) {
      ElMessage.error('继续执行失败')
    }
  }
}

async function handleDebugStep() {
  // 单步执行：调用后端 API 继续到下一个节点
  await handleDebugContinue()
}

async function handleDebugStop() {
  // 停止执行：调用后端 API 取消
  if (execStore.execId) {
    try {
      await wfApi.cancelExecution(execStore.execId)
      debugAbort.value = true
    } catch (error) {
      ElMessage.error('停止执行失败')
    }
  }
}

function handleDragStart(e: DragEvent, nodeType: string) {
  e.dataTransfer?.setData('application/vue-flow', nodeType)
  e.dataTransfer!.effectAllowed = 'move'
}

async function handleNodeSave(node: WfNode) {
  store.updateNode(node.id, node)  // updateNode 内部会调用 markDirty()

  // 自动保存到后端
  if (store.id) {
    try {
      await store.save()
      ElMessage.success('节点配置已保存')
    } catch (error) {
      ElMessage.error('节点配置保存失败')
      console.error('Save node config failed:', error)
    }
  }
}

function handleNodeConfigClose() {
  store.selectedNodeId = ''
}

watch(
  () => store.selectedNodeId,
  (id) => {
    if (id) {
      const node = store.nodes.find(n => n.id === id)
      if (node) {
        selectedNode.value = node
        configVisible.value = true
      }
    } else {
      // 先关闭弹窗，再清空选中的节点
      configVisible.value = false
      // 使用 nextTick 确保组件卸载完成后再清空节点
      nextTick(() => {
        selectedNode.value = null
      })
    }
  }
)
</script>

<template>
  <div class="workflow-editor">
    <div class="editor-topbar">
      <div class="topbar-left">
        <el-button icon="Back" @click="handleBack">返回</el-button>
        <span class="workflow-name">{{ store.name }}</span>
        <el-tag v-if="store.status === 'published'" type="success" size="small">已发布</el-tag>
        <el-tag v-else type="info" size="small">草稿</el-tag>
        <span class="workflow-version">v{{ store.version }}</span>
        <el-tag v-if="store.dirty" type="warning" size="small">未保存</el-tag>
      </div>
      
      <div class="topbar-right">
        <el-button @click="handleUndo" :disabled="store.undoStack.length === 0">撤销</el-button>
        <el-button @click="handleAutoLayout">自动布局</el-button>
        <el-divider direction="vertical" />
        <el-button type="primary" @click="handleExecute(false)" :loading="executing" :disabled="executing">执行</el-button>
        <el-button type="warning" @click="handleExecute(true)" :loading="executing" :disabled="executing || debugPaused">调试</el-button>
        <el-divider direction="vertical" />
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
        <el-button type="success" @click="handlePublish" :loading="publishing">发布</el-button>
      </div>
    </div>
    
    <div class="editor-main">
      <div class="node-palette">
        <h4>基础节点</h4>
        <div class="node-list">
          <div
            v-for="node in basicNodes"
            :key="node.type"
            class="node-item"
            draggable="true"
            @dragstart="(e) => handleDragStart(e, node.type)"
          >
            <el-icon><component :is="node.icon" /></el-icon>
            <span>{{ node.name }}</span>
          </div>
        </div>
        
        <h4>能力节点</h4>
        <div class="node-list">
          <div
            v-for="node in capNodes"
            :key="node.type"
            class="node-item"
            draggable="true"
            @dragstart="(e) => handleDragStart(e, node.type)"
          >
            <el-icon><component :is="node.icon" /></el-icon>
            <span>{{ node.name }}</span>
          </div>
        </div>
      </div>
      
      <div class="canvas-container">
        <WorkflowCanvas class="canvas-area" />
        <DebugToolbar
          @continue="handleDebugContinue"
          @step="handleDebugStep"
          @stop="handleDebugStop"
        />
      </div>
    </div>
    
    <ExecutionPanel />
    
    <NodeConfigModal
      v-if="selectedNode"
      v-model:visible="configVisible"
      :node="selectedNode"
      @save="handleNodeSave"
      @close="handleNodeConfigClose"
    />

    <!-- 开始节点输入参数弹窗 -->
    <el-dialog
      v-model="startInputVisible"
      title="输入执行参数"
      width="500px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div class="start-input-form">
        <p class="start-input-desc">流程的开始节点配置了以下输入参数，请填写后执行：</p>
        <el-form label-position="top">
          <el-form-item
            v-for="variable in startInputVariables"
            :key="variable.name"
            :label="variable.label || variable.name"
            :required="variable.required !== false"
          >
            <el-input
              v-model="startInputValues[variable.name]"
              :placeholder="variable.default ? '默认值: ' + variable.default : '请输入'"
              type="textarea"
              :rows="2"
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="startInputVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmStartInput">确认执行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.workflow-editor {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.editor-topbar {
  height: 56px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 16px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  
  .topbar-left {
    display: flex;
    align-items: center;
    gap: 12px;
    
    .workflow-name {
      font-size: 16px;
      font-weight: 500;
      color: #303133;
    }
    
    .workflow-version {
      font-size: 12px;
      color: #909399;
    }
  }
  
  .topbar-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.editor-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.node-palette {
  width: 280px;
  padding: 16px;
  border-right: 1px solid #ebeef5;
  overflow-y: auto;
  
  h4 {
    margin: 0 0 12px;
    font-size: 13px;
    color: #909399;
    
    &:not(:first-child) {
      margin-top: 20px;
    }
  }
  
  .node-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  
  .node-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    background: #f5f7fa;
    border-radius: 6px;
    cursor: grab;
    transition: all 0.2s;
    
    &:hover {
      background: #ecf5ff;
    }
    
    &:active {
      cursor: grabbing;
    }
    
    .el-icon {
      color: #409eff;
    }
    
    span {
      font-size: 13px;
      color: #303133;
    }
  }
}

.canvas-container {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.canvas-area {
  width: 100%;
  height: 100%;
}

.start-input-form {
  .start-input-desc {
    color: #606266;
    font-size: 13px;
    margin-bottom: 16px;
  }
}
</style>
