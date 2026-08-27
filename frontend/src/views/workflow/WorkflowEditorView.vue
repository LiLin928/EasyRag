<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useWorkflowEditorStore, useWorkflowExecutionStore } from '@/stores/workflow'
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
const debugResolve = ref<(() => void) | null>(null)
const debugAbort = ref(false)
const debugCurrentIndex = ref(0)

const basicNodes = NODE_TYPES.filter(n => n.group === 'basic')

const capNodes = NODE_TYPES.filter(n => n.group === 'cap')

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

// 执行单个节点
async function executeNode(node: WfNode) {
  execStore.updateNodeState(node.id, { status: 'running' })
  execStore.addLog(node.id, 'info', '开始执行节点: ' + node.name)
  
  // 模拟 human 节点等待
  if (node.type === 'human') {
    execStore.addLog(node.id, 'warning', '等待人工介入...')
    execStore.updateNodeState(node.id, { status: 'wait' })
    await new Promise(resolve => setTimeout(resolve, 1500))
  }
  
  await new Promise(resolve => setTimeout(resolve, 800))
  
  const duration = Math.floor(Math.random() * 2000) + 500
  execStore.updateNodeState(node.id, { 
    status: 'success', 
    durationMs: duration
  })
  execStore.addLog(node.id, 'success', '节点执行完成 (' + duration + 'ms)')
}

// 正常执行（全流程）
async function handleExecute(debug: boolean) {
  if (!store.id) {
    ElMessage.warning('请先保存流程')
    return
  }
  
  executing.value = true
  debugAbort.value = false
  execStore.reset()
  execStore.debugMode = debug
  debugCurrentIndex.value = 0
  
  try {
    for (let i = 0; i < store.nodes.length; i++) {
      if (debugAbort.value) {
        execStore.addLog(store.nodes[i].id, 'warning', '执行已中止')
        break
      }
      
      debugCurrentIndex.value = i
      await executeNode(store.nodes[i])
      
      // 调试模式：每个节点执行后暂停
      if (debug) {
        debugPaused.value = true
        execStore.executing = true
        await waitForDebugResume()
        debugPaused.value = false
        
        if (debugAbort.value) {
          execStore.addLog(store.nodes[i].id, 'warning', '执行已中止')
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

// 等待调试继续/单步
function waitForDebugResume(): Promise<void> {
  return new Promise(resolve => {
    debugResolve.value = resolve
  })
}

// 调试：继续执行到结束
function handleDebugContinue() {
  if (debugResolve.value) {
    // 继续模式：跳过后续暂停
    execStore.debugMode = false
    const r = debugResolve.value
    debugResolve.value = null
    r()
  }
}

// 调试：单步执行
function handleDebugStep() {
  if (debugResolve.value) {
    const r = debugResolve.value
    debugResolve.value = null
    r()
  }
}

// 调试：停止执行
function handleDebugStop() {
  debugAbort.value = true
  execStore.debugMode = false
  if (debugResolve.value) {
    const r = debugResolve.value
    debugResolve.value = null
    r()
  }
  executing.value = false
  execStore.executing = false
  debugPaused.value = false
  ElMessage.info('已停止调试')
}

function handleDragStart(event: DragEvent, type: string) {
  event.dataTransfer?.setData('nodeType', type)
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
  }
}

function handleNodeSave(node: WfNode) {
  store.updateNode(node.id, node)
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
    />
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
</style>
