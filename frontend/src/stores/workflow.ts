import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as wfApi from '@/api/workflow'
import type { Workflow, Template, Execution, WfNode, WfEdge, ExecState } from '@/types/workflow'

// ========== 工作流列表 Store ==========

export const useWorkflowListStore = defineStore('workflowList', () => {
  const workflows = ref<Workflow[]>([])
  const templates = ref<Template[]>([])
  const history = ref<Execution[]>([])
  
  const loading = ref(false)
  const activeTab = ref<'list' | 'templates' | 'history'>('list')

  // ========== 加载数据 ==========
  
  async function loadWorkflows() {
    loading.value = true
    try {
      workflows.value = await wfApi.getWorkflows()
    } finally {
      loading.value = false
    }
  }

  async function loadTemplates() {
    const data = await wfApi.getTemplates()
    templates.value = data
  }

  async function loadHistory() {
    const data = await wfApi.getExecutions()
    history.value = data
  }

  // ========== 操作 ==========

  async function createWorkflow(name: string) {
    const wf = await wfApi.createWorkflow({ name })
    workflows.value.unshift(wf)
    return wf
  }

  async function createFromTemplate(templateId: string, name?: string) {
    const wf = await wfApi.createFromTemplate(templateId, name)
    workflows.value.unshift(wf)
    return wf
  }

  async function duplicateWorkflow(id: string) {
    const wf = await wfApi.duplicateWorkflow(id)
    workflows.value.unshift(wf)
    return wf
  }

  async function deleteWorkflow(id: string) {
    await wfApi.deleteWorkflow(id)
    const index = workflows.value.findIndex(w => w.id === id)
    if (index > -1) {
      workflows.value.splice(index, 1)
    }
  }

  return {
    workflows,
    templates,
    history,
    loading,
    activeTab,
    loadWorkflows,
    loadTemplates,
    loadHistory,
    createWorkflow,
    createFromTemplate,
    duplicateWorkflow,
    deleteWorkflow
  }
})

// ========== 工作流编辑器 Store ==========

export const useWorkflowEditorStore = defineStore('workflowEditor', () => {
  const id = ref('')
  const name = ref('')
  const status = ref<'draft' | 'published'>('draft')
  const version = ref(1)
  const dirty = ref(false)
  
  const nodes = ref<WfNode[]>([])
  const edges = ref<WfEdge[]>([])
  
  const undoStack = ref<string[]>([])
  const selectedNodeId = ref('')

  // ========== 节点操作 ==========

  function addNode(type: string, position: { x: number; y: number }) {
    const newNode: WfNode = {
      id: 'node-' + Date.now(),
      type: type as any,
      name: type,
      position,
      data: { rows: [] }
    }
    nodes.value.push(newNode)
    markDirty()
    saveUndo()
    return newNode
  }

  function updateNode(id: string, data: Partial<WfNode>) {
    const node = nodes.value.find(n => n.id === id)
    if (node) {
      Object.assign(node, data)
      markDirty()
    }
  }

  function removeNode(id: string) {
    const index = nodes.value.findIndex(n => n.id === id)
    if (index > -1) {
      nodes.value.splice(index, 1)
      // 删除相关边
      edges.value = edges.value.filter(e => e.source !== id && e.target !== id)
      markDirty()
      saveUndo()
    }
  }

  // ========== 边操作 ==========

  function addEdge(edge: WfEdge) {
    edges.value.push(edge)
    markDirty()
    saveUndo()
  }

  function removeEdge(id: string) {
    const index = edges.value.findIndex(e => e.id === id)
    if (index > -1) {
      edges.value.splice(index, 1)
      markDirty()
      saveUndo()
    }
  }

  // ========== 状态管理 ==========

  function markDirty() {
    dirty.value = true
  }

  function saveUndo() {
    // 保存当前状态快照（简化版：只存 JSON）
    const snapshot = JSON.stringify({ nodes: nodes.value, edges: edges.value })
    undoStack.value.push(snapshot)
    if (undoStack.value.length > 50) {
      undoStack.value.shift()
    }
  }

  function undo() {
    if (undoStack.value.length === 0) return
    const snapshot = JSON.parse(undoStack.value.pop()!)
    nodes.value = snapshot.nodes
    edges.value = snapshot.edges
    dirty.value = true
  }

  // ========== 保存/发布 ==========

  async function save() {
    if (!id.value) return
    await wfApi.updateWorkflow(id.value, {
      nodes: nodes.value,
      edges: edges.value
    })
    dirty.value = false
  }

  async function publish() {
    if (!id.value) return
    const wf = await wfApi.publishWorkflow(id.value)
    status.value = wf.status
    version.value = wf.version
    dirty.value = false
  }

  // ========== 加载 ==========

  async function load(workflowId: string) {
    const wf = await wfApi.getWorkflow(workflowId)
    id.value = wf.id
    name.value = wf.name
    status.value = wf.status
    version.value = wf.version
    nodes.value = wf.nodes || []
    edges.value = wf.edges || []
    dirty.value = false
    undoStack.value = []
  }

  // ========== 导出/导入 ==========

  function toDefinition() {
    return {
      nodes: nodes.value,
      edges: edges.value
    }
  }

  function fromDefinition(def: { nodes: WfNode[]; edges: WfEdge[] }) {
    nodes.value = def.nodes
    edges.value = def.edges
    markDirty()
  }

  return {
    id,
    name,
    status,
    version,
    dirty,
    nodes,
    edges,
    undoStack,
    selectedNodeId,
    addNode,
    updateNode,
    removeNode,
    addEdge,
    removeEdge,
    markDirty,
    undo,
    save,
    publish,
    load,
    toDefinition,
    fromDefinition
  }
})

// ========== 工作流执行 Store ==========

export const useWorkflowExecutionStore = defineStore('workflowExecution', () => {
  const executing = ref(false)
  const debugMode = ref(false)
  const execId = ref('')
  const nodeStates = ref<ExecState>({})
  const logs = ref<{ time: string; nodeId: string; level: string; content: string }[]>([])

  function reset() {
    executing.value = false
    execId.value = ''
    nodeStates.value = {}
    logs.value = []
  }

  function updateNodeState(nodeId: string, state: { status: any; durationMs?: number; output?: string }) {
    nodeStates.value[nodeId] = state
  }

  function addLog(nodeId: string, level: string, content: string) {
    logs.value.push({
      time: new Date().toISOString(),
      nodeId,
      level,
      content
    })
  }

  return {
    executing,
    debugMode,
    execId,
    nodeStates,
    logs,
    reset,
    updateNodeState,
    addLog
  }
})

