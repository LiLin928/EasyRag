// 知识库模块类型定义

export type MetadataScope = 'document' | 'chunk'
export type MetadataDataType = 'string' | 'number' | 'date' | 'select' | 'boolean'
export type RetrievalMethod = 'vector' | 'keyword' | 'hybrid'
export type TestRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'canceled'
export type TestCaseStatus =
  | 'pending'
  | 'running'
  | 'hit'
  | 'partial_hit'
  | 'miss'
  | 'failed'
  | 'skipped'

export interface KnowledgeBase {
  id: string
  name: string
  description: string | null
  scene: string
  cover: string | null
  doc_count: number
  total_size: number
  chunk_count: number
  last_test_at: string | null
  created_at: string

  // Temporary aliases for the legacy knowledge page; remove in Task 10.
  desc: string
  docCount?: number
  totalSize?: string
  createdAt?: string
}

export interface MetadataField {
  id: string
  kb_id: string
  key: string
  name: string
  scope: MetadataScope
  data_type: MetadataDataType
  options: string[]
  default_value: unknown
  required: boolean
  filterable: boolean
  retrieval_filterable: boolean
  visible: boolean
  built_in: boolean
  mapped_field: string | null
  sort_order: number
}

export type MetadataFieldPayload = Omit<
  MetadataField,
  'id' | 'kb_id' | 'built_in' | 'mapped_field'
>

export interface DocumentAsset {
  id: string
  kb_id: string
  name: string
  ext: string
  size: number
  pages: number
  mode: 'fast' | 'precision'
  status: 'pending' | 'parsing' | 'done' | 'failed'
  pct: number
  element_count: number
  chunk_count: number
  metadata: Record<string, unknown>
  enabled: boolean
  recall_count: number
  created_at: string
}

export interface Document extends DocumentAsset {
  // Temporary aliases for the legacy document table; remove in Task 10.
  kbId?: string
  sizeLabel?: string
  elementCount?: number
  createdAt?: string
}

export interface ChunkAsset {
  id: string
  kb_id: string
  document_id: string
  document_name: string
  content: string
  content_search: string | null
  clause_title: string | null
  section_path: string | null
  page_number: number
  seq: number
  char_count: number
  embedding_model: string | null
  metadata: Record<string, unknown>
  enabled: boolean
  recall_count: number
  created_at: string
}

export interface ConfigSource {
  value: string | number | boolean
  source: 'override' | 'knowledge_base' | 'scene' | 'system_default'
}

export interface RetrievalSettings {
  values: Record<string, ConfigSource>
  resolved: Record<string, string | number | boolean>
  embedding_model: {
    id: string
    name: string
    prov: string
    params: Record<string, unknown>
  } | null
  rerank_model: { id: string; name: string; prov: string } | null
  rebuild_required: boolean
}

export interface RetrievalSettingsPayload {
  embedding_model_id?: string | null
  rerank_model_id?: string | null
  retrieval_config?: Record<string, unknown> | null
}

export interface RetrievalTestSet {
  id: string
  kb_id: string
  name: string
  description: string | null
  archived: boolean
  case_count: number
  last_run_at: string | null
  last_metrics: Record<string, Record<string, number | null>> | null
  created_at: string
  updated_at: string
}

export type RetrievalTestSetPayload = Partial<
  Pick<RetrievalTestSet, 'name' | 'description' | 'archived'>
>

export interface RetrievalTestCase {
  id: string
  test_set_id: string
  query: string
  expected_doc_ids: string[]
  expected_chunk_ids: string[]
  tags: string[]
  enabled: boolean
  sort_order: number
  first_expected_hit_rank?: number | null
  status?: TestCaseStatus
  latency_ms?: number | null
  last_run_at?: string | null
  created_at: string
  updated_at: string
}

export type RetrievalTestCasePayload = Partial<
  Pick<
    RetrievalTestCase,
    | 'query'
    | 'expected_doc_ids'
    | 'expected_chunk_ids'
    | 'tags'
    | 'enabled'
    | 'sort_order'
  >
>

export interface RetrievalCandidate {
  rank: number
  chunk_id: string
  document_id: string
  document_name: string
  section_path: string | null
  page_number: number
  char_count: number
  vector_score: number | null
  keyword_score: number | null
  vector_rank: number | null
  keyword_rank: number | null
  rrf_score: number | null
  rerank_score: number | null
  metadata: Record<string, unknown>
}

export interface RetrievalTestCaseResult extends RetrievalTestCase {
  run_id: string
  hit_doc_ids: string[]
  results: RetrievalCandidate[]
  metrics: Record<string, unknown>
  error: string | null
}

export interface RetrievalTestRun {
  id: string
  test_set_id: string
  kb_id: string
  status: TestRunStatus
  config_snapshot: {
    settings: RetrievalSettings
    ks: number[]
    embedding_model: { id: string; name: string; prov: string; dim?: number | null } | null
    rerank_model: { id: string; name: string; prov: string } | null
    document_metadata: Record<string, unknown>
    chunk_metadata: Record<string, unknown>
  }
  override_config: Record<string, unknown>
  total_cases: number
  completed_cases: number
  metrics: Record<string, Record<string, number | null> | number | null>
  error: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface RetrievalRunPayload {
  case_ids?: string[]
  ks?: number[]
  override_config?: Record<string, unknown>
  document_metadata?: Record<string, unknown>
  chunk_metadata?: Record<string, unknown>
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
