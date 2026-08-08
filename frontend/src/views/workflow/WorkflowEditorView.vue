<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useWorkflowEditorStore, useWorkflowExecutionStore } from '@/stores/workflow'
import WorkflowCanvas from './components/WorkflowCanvas.vue'
import NodeConfigModal from './components/NodeConfigModal.vue'
import ExecutionPanel from './components/ExecutionPanel.vue'
import DebugToolbar from './components/DebugToolbar.vue'
import type { NodeType, WfNode } from '@/types/workflow'

const route = useRoute()
const router = useRouter()
const store = useWorkflowEditorStore()
const execStore = useWorkflowExecutionStore()

const saving = ref(false)
const publishing = ref(false)
const executing = ref(false)
const configVisible = ref(false)
const selectedNode = ref<WfNode | null>(null)

const basicNodes: { type: NodeType; name: string; icon: string }[] = [
  { type: 'start', name: '开始', icon: 'VideoPlay' },
  { type: 'end', name: '结束', icon: 'VideoPause' },
  { type: 'condition', name: '条件分支', icon: 'Share' },
  { type: 'loop', name: '循环', icon: 'Refresh' },
  { type: 'human', name: '人工介入', icon: 'User' },
  { type: 'variable_assign', name: '变量赋值', icon: 'Edit' },
  { type: 'template_render', name: '模板渲染', icon: 'Document' }
]

const capNodes: { type: NodeType; name: string; icon: string }[] = [
  { type: 'llm', name: 'LLM 生成', icon: 'ChatDotSquare' },
  { type: 'rag', name: 'RAG 检索', icon: 'Search' },
  { type: 'code', name: '代码执行', icon: 'Cpu' },
  { type: 'http', name: 'HTTP 请求', icon: 'Link' },
  { type: 'tool', name: '外部工具', icon: 'Setting' }
]

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

async function handleExecute(debug: boolean) {
  if (!store.id) {
    ElMessage.warning('请先保存流程')
    return
  }
  
  executing.value = true
  execStore.reset()
  execStore.debugMode = debug
  
  try {
    for (const node of store.nodes) {
      execStore.updateNodeState(node.id, { status: 'running' })
      execStore.addLog(node.id, 'info', '开始执行节点: ' + node.name)
      
      await new Promise(resolve => setTimeout(resolve, 1000))
      
      execStore.updateNodeState(node.id, { 
        status: 'success', 
        durationMs: Math.floor(Math.random() * 2000) + 500
      })
      execStore.addLog(node.id, 'success', '节点执行完成')
      
      if (debug) {
        break
      }
    }
    
    ElMessage.success('执行完成')
  } catch (error) {
    ElMessage.error('执行失败')
  } finally {
    executing.value = false
    execStore.executing = false
  }
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
        <el-button type="primary" @click="handleExecute(false)" :loading="executing">执行</el-button>
        <el-button type="warning" @click="handleExecute(true)" :loading="executing">调试</el-button>
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
        <DebugToolbar />
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
