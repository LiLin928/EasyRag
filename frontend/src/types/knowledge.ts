// ============================================================
// 知识库模块类型定义
// ============================================================

// ---------- 枚举 ----------

/** 分段方式 */
export type ChunkMethod = 'general' | 'parent_child' | 'qa'

/** 检索模式 */
export type RetrievalMethod = 'vector' | 'hybrid' | 'keyword'

/** 配置来源优先级 */
export type ConfigSource = 'override' | 'knowledge_base' | 'scene' | 'system_default'

/** 元数据字段类型 */
export type MetadataFieldType = 'string' | 'number' | 'date' | 'select' | 'boolean'

/** 元数据作用域 */
export type MetadataScope = 'document' | 'chunk'

// ---------- 基础泛型 ----------

/** 生效值（带来源标记），用于检索设置回显 */
export interface EffectiveValue<T> {
  value: T
  source: ConfigSource
}

// ---------- 检索配置 ----------

/** 检索参数（知识库级覆盖） */
export interface RetrievalConfig {
  method: RetrievalMethod
  vectorTopK: number
  keywordTopK: number
  similarityThreshold: number
  similarityThresholdEnabled: boolean
  vectorWeight: number
  keywordWeight: number
  rrfK: number
  rerankEnabled: boolean
  rerankTopN: number
  rerankTriggerThreshold: number
  navigationEnabled: boolean
  navAnchorCount: number
  navConfidenceThreshold: number
}

/** 知识库检索设置（返回时每项带来源） */
export interface RetrievalSettings {
  embeddingModel: string
  rerankModel: string
  chunkMethod: ChunkMethod
  chunkSize: number
  chunkOverlap: number
  config: Record<string, EffectiveValue<string | number | boolean>>
}

// ---------- 元数据 ----------

/** 元数据字段定义 */
export interface MetadataField {
  id: string
  kbId: string
  key: string
  name: string
  scope: MetadataScope
  dataType: MetadataFieldType
  options: string[]
  defaultValue?: string
  required: boolean
  filterable: boolean
  retrievalFilterable: boolean
  visible: boolean
  builtIn: boolean
  mappedField?: string
  sortOrder: number
}

// ---------- 知识库 ----------

export interface KnowledgeBase {
  id: string
  name: string
  desc: string
  scene: string
  docCount: number
  totalSize: string
  createdAt: string
  cover: string
  // 新增字段
  embeddingModel?: string
  rerankModel?: string
  chunkMethod?: ChunkMethod
  retrievalConfig?: Partial<RetrievalConfig>
  segmentCount?: number
  lastTestTime?: string
}

// ---------- 文档 ----------

export interface Document {
  id: string
  kbId: string
  name: string
  ext: string
  size: string
  pages: number
  mode: 'fast' | 'precision'
  status: 'done' | 'parsing' | 'failed' | 'pending'
  pct?: number
  elementCount: number
  createdAt: string
  // 新增字段
  enabled?: boolean
  recallCount?: number
  metadata?: Record<string, string>
  charCount?: number
  segmentMode?: ChunkMethod
}

// ---------- 分段 ----------

export interface Segment {
  id: string
  docId: string
  kbId: string
  parentId?: string
  seq: number
  type: 'text' | 'parent' | 'qa'
  content: string
  charCount: number
  embeddingModel?: string
  recallCount: number
  enabled: boolean
  metadata: Record<string, string>
  question?: string
  answer?: string
  children?: Segment[]
}

// ---------- 召回测试（即时） ----------

export interface HitTestSegment {
  id: string
  docId: string
  docName: string
  content: string
  charCount: number
  score: number
  vectorScore?: number
  keywordScore?: number
  rerankScore?: number
  children?: HitTestSegment[]
}

export interface HitTestResult {
  query: string
  retrievalMode: RetrievalMethod
  segments: HitTestSegment[]
}

export interface HitTestRecord {
  id: string
  kbId: string
  query: string
  source: 'immediate' | 'batch'
  retrievalMode: RetrievalMethod
  createdAt: string
  result?: HitTestResult
}

// ---------- 召回测试（批量） ----------

export interface RetrievalTestSet {
  id: string
  kbId: string
  name: string
  description?: string
  caseCount: number
  lastRunTime?: string
  lastMetrics?: TestMetrics
  status: 'draft' | 'latest' | 'archived'
}

export interface RetrievalTestCase {
  id: string
  testSetId: string
  query: string
  expectedDocIds: string[]
  expectedChunkIds: string[]
  tags: string[]
  enabled: boolean
  lastHitRank?: number
  lastStatus?: 'hit' | 'partial_hit' | 'miss' | 'failed' | 'skipped'
  lastLatency?: number
}

export interface TestMetrics {
  hitAtK: number
  recallAtK: number
  mrr: number
  p50Latency: number
  p95Latency: number
  rerankTriggerRate: number
  failureRate: number
}

export interface RetrievalTestRun {
  id: string
  testSetId: string
  kbId: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'canceled'
  totalCases: number
  completedCases: number
  metrics?: TestMetrics
  error?: string
  startedAt?: string
  finishedAt?: string
  createdAt: string
}

// ---------- 结构树与元素（保留原有） ----------

export interface TreeNode {
  node_id: string
  title: string
  level: number
  summary?: string
  element_count: number
  children: TreeNode[]
}

export interface DocElement {
  element_id: string
  doc_title: string
  type: string
  content: string
  node_id: string
  node_title: string
  page_number: number
  seq: number
}

// ---------- 解析任务（保留原有） ----------

export interface ParseTask {
  task_id: string
  doc_id: string
  status: 'pending' | 'parsing' | 'done' | 'failed'
  pct: number
}
