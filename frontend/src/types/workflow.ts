// ========== 工作流节点类型 ==========

export type NodeType =
  | 'start'
  | 'end'
  | 'condition'
  | 'loop'
  | 'human'
  | 'variable_assign'
  | 'template_render'
  | 'llm'
  | 'rag'
  | 'code'
  | 'http'
  | 'tool'

export type NodeGroup = 'basic' | 'cap'

export interface NodeTypeInfo {
  type: NodeType
  name: string
  group: NodeGroup
  color: string
  icon: string
}

export const NODE_TYPES: NodeTypeInfo[] = [
  { type: 'start', name: '开始', group: 'basic', color: '#334155', icon: 'VideoPlay' },
  { type: 'end', name: '结束', group: 'basic', color: '#334155', icon: 'VideoPause' },
  { type: 'condition', name: '条件分支', group: 'basic', color: '#CA8A04', icon: 'Share' },
  { type: 'loop', name: '循环', group: 'basic', color: '#0891B2', icon: 'Refresh' },
  { type: 'human', name: '人工介入', group: 'basic', color: '#7C3AED', icon: 'User' },
  { type: 'variable_assign', name: '变量赋值', group: 'basic', color: '#64748B', icon: 'Edit' },
  { type: 'template_render', name: '模板渲染', group: 'basic', color: '#B45309', icon: 'Document' },
  { type: 'llm', name: 'LLM 生成', group: 'cap', color: '#0369A1', icon: 'ChatDotSquare' },
  { type: 'rag', name: 'RAG 检索', group: 'cap', color: '#0D9488', icon: 'Search' },
  { type: 'code', name: '代码执行', group: 'cap', color: '#BE123C', icon: 'Cpu' },
  { type: 'http', name: 'HTTP 请求', group: 'cap', color: '#C2410C', icon: 'Link' },
  { type: 'tool', name: '外部工具', group: 'cap', color: '#9D174D', icon: 'Setting' }
]

// ========== 工作流定义 ==========

export interface WfNode {
  id: string
  type: NodeType
  name: string
  position: { x: number; y: number }
  data: {
    rows: [string, string][] // 配置项预览行
    config?: any // 详细配置
  }
}

export interface WfEdge {
  id: string
  source: string
  target: string
  label?: string
  sourceHandle?: 'l' | 'r' // 条件分支双出口
}

export interface Workflow {
  id: string
  name: string
  description?: string
  status: 'draft' | 'published'
  version: number
  icon?: string
  nodes: WfNode[]
  edges: WfEdge[]
  successRate?: number
  lastRun?: string
  createdAt: string
  updatedAt: string
}

// ========== 模板 ==========

export type TemplateSource = 'official' | 'community'

export interface Template {
  id: string
  name: string
  description?: string
  source: TemplateSource
  tags: string[]
  nodeCount: number
  useCount: number
  thumbnail?: string
  definition: {
    nodes: WfNode[]
    edges: WfEdge[]
  }
}

// ========== 执行历史 ==========

export type ExecTrigger = 'manual' | 'schedule' | 'api' | 'agent'
export type ExecStatus = 'running' | 'success' | 'error' | 'wait' | 'cancelled'

export interface Execution {
  id: string
  workflowId: string
  workflowName: string
  status: ExecStatus
  trigger: ExecTrigger
  startTime: string
  duration?: number // ms
  nodeProgress: string // e.g. "4/7"
}

// ========== 执行状态（编辑器用）==========

export type NodeExecStatus = 'idle' | 'running' | 'success' | 'error' | 'wait'

export interface NodeExecState {
  status: NodeExecStatus
  durationMs?: number
  output?: string
}

export interface ExecState {
  [nodeId: string]: NodeExecState
}

// ========== SSE 事件 ==========

export interface ExecStartEvent {
  event: 'execution_start'
  total_nodes: number
}

export interface NodeStartEvent {
  event: 'node_start'
  node_id: string
  node_name: string
}

export interface NodeProgressEvent {
  event: 'node_progress'
  node_id: string
  progress: number
  message?: string
}

export interface NodeCompleteEvent {
  event: 'node_complete'
  node_id: string
  status: 'success' | 'error'
  duration_ms: number
  output?: string
}

export interface NodeErrorEvent {
  event: 'node_error'
  node_id: string
  error: string
  retry_count?: number
}

export interface ExecPausedEvent {
  event: 'execution_paused'
  node_id: string
  reason: 'human_input' | 'approval'
}

export interface ExecResumedEvent {
  event: 'execution_resumed'
  node_id: string
}

export interface ExecCompleteEvent {
  event: 'execution_complete'
  success: boolean
  total_duration_ms: number
}

export interface ExecErrorEvent {
  event: 'execution_error'
  error: string
}

export type WfExecEvent =
  | ExecStartEvent
  | NodeStartEvent
  | NodeProgressEvent
  | NodeCompleteEvent
  | NodeErrorEvent
  | ExecPausedEvent
  | ExecResumedEvent
  | ExecCompleteEvent
  | ExecErrorEvent
