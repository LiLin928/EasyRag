// 对话模块类型定义

// 会话
export interface Conversation {
  id: string
  title: string
  lastTime: string
  msgCount: number
  agentId?: string           // 关联的智能体 ID（可选）
  agentName?: string         // 智能体名称（用于显示）
}

// 消息
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  references?: Reference[]
  phase?: Phase
  trace?: TraceInfo
  usage?: Usage
  ts: string
}

// 阶段
export type Phase = 'idle' | 'parse' | 'navigate' | 'retrieve' | 'generate'

// 引用
export interface Reference {
  ref_id: string
  element_id: string
  doc_title: string
  node_title: string
  content_preview: string
  score: number
  type: 'text' | 'table' | 'image'
}

// 追踪信息
export interface TraceInfo {
  trace_id: string
  nav_ms: number
  retrieve_ms: number
  generate_ms: number
  total_ms: number
}

// 使用量
export interface Usage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

// 场景
export interface Scene {
  id: string
  name: string
  desc: string
}

// SSE 事件类型
export type SSEEventType = 'phase' | 'navigation' | 'references' | 'token' | 'done' | 'trace' | 'error'

// SSE 事件数据
export interface SSEEvent {
  event: SSEEventType
  data: any
}
