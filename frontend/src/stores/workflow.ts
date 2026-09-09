import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as wfApi from '@/api/workflow'
import type { Workflow, Template, Execution, WfNode, WfEdge, ExecState } from '@/types/workflow'
import { NODE_TYPES } from '@/types/workflow'

// ========== 工作流列表 Store ==========

export const useWorkflowListStore = defineStore('workflowList', () => {
  const workflows = ref<Workflow[]>([])
  const templates = ref<Template[]>([])
  const history = ref<Execution[]>([])
  
  const loading = ref(false)
  const activeTab = ref<'list' | 'templates' | 'history'>('list')

  // ========== 搜索 ==========

  const keyword = ref('')
  const tplKeyword = ref('')

  // 按关键词过滤的流程列表（名称 / 描述）
  const filteredWorkflows = computed(() => {
    if (!keyword.value.trim()) return workflows.value
    const kw = keyword.value.toLowerCase()
    return workflows.value.filter(w =>
      w.name.toLowerCase().includes(kw) ||
      (w.description || '').toLowerCase().includes(kw)
    )
  })

  // 按关键词过滤的模板列表（名称 / 描述 / 标签）
  const filteredTemplates = computed(() => {
    if (!tplKeyword.value.trim()) return templates.value
    const kw = tplKeyword.value.toLowerCase()
    return templates.value.filter(t =>
      t.name.toLowerCase().includes(kw) ||
      (t.description || '').toLowerCase().includes(kw) ||
      t.tags.some(tag => tag.toLowerCase().includes(kw))
    )
  })

  // ========== 数据加载 ==========
  
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

  // ========== 流程操作 ==========

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
    keyword,
    tplKeyword,
    filteredWorkflows,
    filteredTemplates,
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

  function addNode(type: string, position: { x: number; y: number }) {
    const newNode: WfNode = {
      id: 'node-' + Date.now(),
      type: type as any,
      name: NODE_TYPES.find(n => n.type === type)?.name || type,
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
      edges.value = edges.value.filter(e => e.source !== id && e.target !== id)
      markDirty()
      saveUndo()
    }
  }

  function addEdge(edge: WfEdge) {
    edges.value.push(edge)
    markDirty()
    saveUndo()
  }

  function insertNodeBetween(edgeId: string, nodeType: string) {
    const edge = edges.value.find(e => e.id === edgeId)
    if (!edge) return

    const sourceNode = nodes.value.find(n => n.id === edge.source)
    const targetNode = nodes.value.find(n => n.id === edge.target)
    if (!sourceNode || !targetNode) return

    const midPos = {
      x: (sourceNode.position.x + targetNode.position.x) / 2,
      y: (sourceNode.position.y + targetNode.position.y) / 2
    }

    const newNode: WfNode = {
      id: 'node-' + Date.now(),
      type: nodeType as any,
      name: NODE_TYPES.find(n => n.type === nodeType)?.name || nodeType,
      position: midPos,
      data: { rows: [] }
    }
    nodes.value.push(newNode)

    edges.value = edges.value.filter(e => e.id !== edgeId)

    const newEdge1: WfEdge = {
      id: 'e-' + Date.now() + '-1',
      source: edge.source,
      target: newNode.id,
      sourceHandle: edge.sourceHandle
    }
    const newEdge2: WfEdge = {
      id: 'e-' + Date.now() + '-2',
      source: newNode.id,
      target: edge.target
    }
    edges.value.push(newEdge1, newEdge2)

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

  function markDirty() {
    dirty.value = true
  }

  function saveUndo() {
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
    id, name, status, version, dirty, nodes, edges, undoStack, selectedNodeId,
    addNode, updateNode, removeNode, addEdge, removeEdge, insertNodeBetween, markDirty, undo, save, publish, load, toDefinition, fromDefinition
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
    executing, debugMode, execId, nodeStates, logs,
    reset, updateNodeState, addLog
  }
})
