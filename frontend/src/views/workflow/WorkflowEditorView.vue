<script setup lang="ts">
import { onMounted, ref, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useWorkflowEditorStore, useWorkflowExecutionStore } from '@/stores/workflow'
import WorkflowCanvas from './components/WorkflowCanvas.vue'
import NodeConfigModal from './components/NodeConfigModal.vue'
import ExecutionPanel from './components/ExecutionPanel.vue'
import DebugToolbar from './components/DebugToolbar.vue'
import type { WfNode, WfEdge } from '@/types/workflow'
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
const debugResolve = ref<(() => void) | null>(null)
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
})

function handleBack() {
  router.push('/workflows')
}

async function handleSave() {
  if (!store.id) {
    ElMessage.warning('请先保存流程')
    return
  }
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
  if (!store.id) {
    ElMessage.warning('请先保存流程')
    return
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
  if (!store.id) {
    ElMessage.warning('请先保存流程')
    return
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

// 实际执行流程
async function doExecute(debug: boolean, inputs: Record<string, any>) {
  executing.value = true
  debugAbort.value = false
  execStore.reset()
  execStore.debugMode = debug
  debugCurrentIndex.value = 0
  
  try {
    const executionOrder = getExecutionOrder(store.nodes, store.edges)
    
    for (let i = 0; i < executionOrder.length; i++) {
      const node = executionOrder[i]
      
      if (debugAbort.value) {
        execStore.addLog(node.id, 'warning', '执行已中止')
        break
      }
      
      debugCurrentIndex.value = i
      await executeNode(node, inputs)
      
      // 调试模式：每个节点执行后暂停
      if (debug) {
        debugPaused.value = true
        execStore.executing = true
        await waitForDebugResume()
        debugPaused.value = false
        
        if (debugAbort.value) {
          execStore.addLog(node.id, 'warning', '执行已中止')
          break
        }
      }
    }
    
    if (!debugAbort.value) {
      ElMessage.success('执行完成')
    }
  } catch (error) {
    ElMessage.error('执行失败')
  } finally {
    executing.value = false
    execStore.executing = false
    debugPaused.value = false
  }
}

// 获取节点的执行顺序（拓扑排序，从 start 开始）
function getExecutionOrder(nodes: WfNode[], edges: WfEdge[]): WfNode[] {
  const nodeMap = new Map(nodes.map(n => [n.id, n]))
  const adjacencyList = new Map<string, string[]>()
  const inDegree = new Map<string, number>()
  
  // 初始化
  nodes.forEach(n => {
    adjacencyList.set(n.id, [])
    inDegree.set(n.id, 0)
  })
  
  // 构建邻接表和入度
  edges.forEach(e => {
    adjacencyList.get(e.source)?.push(e.target)
    inDegree.set(e.target, (inDegree.get(e.target) || 0) + 1)
  })
  
  // 找到 start 节点作为起点
  const startNode = nodes.find(n => n.type === 'start')
  if (!startNode) return nodes // 没有 start 节点，按原顺序返回
  
  // 从 start 节点开始 BFS
  const order: WfNode[] = []
  const visited = new Set<string>()
  const queue: string[] = [startNode.id]
  
  while (queue.length > 0) {
    const currentId = queue.shift()!
    if (visited.has(currentId)) continue
    visited.add(currentId)
    
    const node = nodeMap.get(currentId)
    if (node) order.push(node)
    
    // 获取下一层节点
    const nextIds = adjacencyList.get(currentId) || []
    // 条件分支：yes 优先于 no
    const sortedNextIds = nextIds.sort((a, b) => {
      const edgeA = edges.find(e => e.source === currentId && e.target === a)
      const edgeB = edges.find(e => e.source === currentId && e.target === b)
      if (edgeA?.sourceHandle === 'yes' && edgeB?.sourceHandle !== 'yes') return -1
      if (edgeB?.sourceHandle === 'yes' && edgeA?.sourceHandle !== 'yes') return 1
      return 0
    })
    
    sortedNextIds.forEach(id => {
      if (!visited.has(id)) {
        queue.push(id)
      }
    })
  }
  
  return order
}

// 模拟执行单个节点，返回执行结果
async function executeNode(node: WfNode, inputs?: Record<string, any>): Promise<any> {
  execStore.updateNodeState(node.id, { status: 'running' })
  execStore.addLog(node.id, 'info', '开始执行节点: ' + node.name)
  
  // 模拟 start 节点输入
  if (node.type === 'start' && inputs) {
    execStore.addLog(node.id, 'info', '输入参数: ' + JSON.stringify(inputs))
    await delay(100)
    execStore.updateNodeState(node.id, { status: 'success', output: JSON.stringify(inputs) })
    execStore.addLog(node.id, 'success', '节点执行完成: ' + node.name)
    return inputs
  }
  
  // 模拟 human 节点等待
  if (node.type === 'human') {
    execStore.addLog(node.id, 'warning', '等待人工介入...')
    execStore.updateNodeState(node.id, { status: 'wait' })
    await delay(500)
    execStore.updateNodeState(node.id, { status: 'success', output: '{"result": "approved"}' })
    execStore.addLog(node.id, 'success', '人工介入完成')
    return { result: 'approved' }
  }
  
  // 模拟条件分支
  if (node.type === 'condition') {
    await delay(300)
    const result = Math.random() > 0.3 // 70% 概率为 true
    execStore.updateNodeState(node.id, { status: 'success', output: JSON.stringify({ result }) })
    execStore.addLog(node.id, 'result', '条件判断结果: ' + (result ? '是' : '否'))
    return { result }
  }
  
  // 模拟 LLM 节点
  if (node.type === 'llm') {
    await delay(2000)
    const output = {
      result: '分析完成',
      content: '这是一个模拟的 LLM 输出内容...'
    }
    execStore.updateNodeState(node.id, { status: 'success', output: JSON.stringify(output) })
    execStore.addLog(node.id, 'result', 'LLM 输出: ' + JSON.stringify(output).slice(0, 100) + '...')
    return output
  }
  
  // 模拟其他节点
  await delay(500 + Math.random() * 1000)
  const genericOutput = { result: node.type + '_completed' }
  execStore.updateNodeState(node.id, { status: 'success', output: JSON.stringify(genericOutput) })
  execStore.addLog(node.id, 'success', '节点执行完成: ' + node.name)
  return genericOutput
}

function delay(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function waitForDebugResume(): Promise<void> {
  return new Promise((resolve) => {
    debugResolve.value = resolve
  })
}

function handleDebugContinue() {
  if (debugResolve.value) {
    debugResolve.value()
    debugResolve.value = null
  }
}

function handleDebugStep() {
  handleDebugContinue()
}

function handleDebugStop() {
  debugAbort.value = true
  handleDebugContinue()
}

function handleDragStart(e: DragEvent, nodeType: string) {
  e.dataTransfer?.setData('application/vue-flow', nodeType)
  e.dataTransfer!.effectAllowed = 'move'
}

function handleNodeSave(node: WfNode) {
  store.updateNode(node.id, node)
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
      configVisible.value = false
      selectedNode.value = null
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
