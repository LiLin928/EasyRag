// 知识库模块类型定义

// 知识库
export interface KnowledgeBase {
  id: string
  name: string
  desc: string
  scene: string          // 关联场景预设
  docCount: number
  totalSize: string
  createdAt: string
  cover?: string         // 知识库封面色/图
}

// 文档
export interface Document {
  id: string
  kbId: string
  name: string
  ext: 'pdf' | 'docx' | 'md' | 'txt' | 'xlsx'
  size: string
  pages: number
  mode: 'fast' | 'precision'   // 解析模式
  status: 'done' | 'parsing' | 'failed' | 'pending'
  pct?: number                 // 解析进度
  elementCount: number
  createdAt: string
}

// 结构树节点
export interface TreeNode {
  node_id: string
  title: string
  level: number
  summary?: string | null
  element_count: number
  children: TreeNode[]
}

// 文档元素
export interface DocElement {
  element_id: string
  doc_title: string
  type: 'text' | 'table' | 'image' | 'heading'
  content: string
  node_id: string
  node_title: string
  page_number: number
  seq: number
  prev_element_id?: string
  next_element_id?: string
}

// 解析任务
export interface ParseTask {
  task_id: string
  doc_id: string
  status: 'pending' | 'parsing' | 'done' | 'failed'
  pct: number
  error?: string
}

// 上传参数
export interface UploadParams {
  kbId: string
  files: File[]
  mode: 'fast' | 'precision'
  scene?: string
}
