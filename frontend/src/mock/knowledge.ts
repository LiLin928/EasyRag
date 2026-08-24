// 知识库 Mock：可变内存状态，不依赖浏览器 API 或定时器
import type {
  ChunkAsset,
  DocumentAsset,
  Document,
  KnowledgeBase,
  MetadataDataType,
  MetadataField,
  MetadataScope,
  RetrievalCandidate,
  RetrievalSettings,
  RetrievalTestCase,
  RetrievalTestCaseResult,
  RetrievalTestRun,
  RetrievalTestSet,
} from '@/types/knowledge'

type Data = Record<string, unknown>
type Envelope = { code: number; message: string; data: unknown }

function ok(data: unknown): Envelope {
  return { code: 0, message: 'success', data }
}

function invalid(message: string): Envelope {
  return { code: 40001, message, data: null }
}

function notFound(message: string): Envelope {
  return { code: 40400, message, data: null }
}

function isRecord(value: unknown): value is Data {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function text(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function optionalText(value: unknown): string | null {
  return typeof value === 'string' && value ? value : null
}

function booleanValue(value: unknown, fallback = false): boolean {
  return typeof value === 'boolean' ? value : fallback
}

function numberValue(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

function numberList(value: unknown): number[] {
  return Array.isArray(value)
    ? value.filter((item): item is number => typeof item === 'number' && Number.isFinite(item))
    : []
}

function formatSize(size: number): string {
  if (size >= 1024 * 1024) return (size / 1024 / 1024).toFixed(1) + ' MB'
  if (size >= 1024) return (size / 1024).toFixed(1) + ' KB'
  return size + ' B'
}

let idSeed = 1000
let timeSeed = 0

function nextId(prefix: string): string {
  idSeed += 1
  return `${prefix}${idSeed}`
}

function nextTime(): string {
  timeSeed += 1
  const minute = String(Math.floor(timeSeed / 60)).padStart(2, '0')
  const second = String(timeSeed % 60).padStart(2, '0')
  return `2026-08-24T08:${minute}:${second}.000Z`
}

function isEnvelope(value: unknown): value is Envelope {
  return typeof value === 'object' && value !== null && 'code' in value
}

function removeInPlace<T>(items: T[], predicate: (item: T) => boolean): void {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    if (predicate(items[index])) items.splice(index, 1)
  }
}

function withKbAliases(kb: KnowledgeBase): KnowledgeBase {
  return {
    ...kb,
    desc: kb.description || '',
    docCount: kb.doc_count,
    totalSize: formatSize(kb.total_size),
    createdAt: kb.created_at,
  }
}

function withDocumentAliases(document: Document): Document {
  return {
    ...document,
    kbId: document.kb_id,
    sizeLabel: formatSize(document.size),
    elementCount: document.element_count,
    createdAt: document.created_at,
  }
}

export const mockKbs: KnowledgeBase[] = [
  withKbAliases({
    id: 'kb1',
    name: '标书知识库',
    description: '招投标相关文档，包括招标文件、投标文件、评标报告等',
    desc: '',
    scene: 'bidding',
    cover: '#409eff',
    doc_count: 3,
    total_size: 11_612_160,
    chunk_count: 9,
    last_test_at: '2026-08-20T09:30:00.000Z',
    created_at: '2026-07-15T10:30:00.000Z',
  }),
  withKbAliases({
    id: 'kb2',
    name: '合同知识库',
    description: '各类合同模板和已签署合同文档',
    desc: '',
    scene: 'contract',
    cover: '#67c23a',
    doc_count: 0,
    total_size: 0,
    chunk_count: 0,
    last_test_at: null,
    created_at: '2026-07-18T14:20:00.000Z',
  }),
  withKbAliases({
    id: 'kb3',
    name: '通用知识库',
    description: '公司通用文档、制度规范、操作手册等',
    desc: '',
    scene: 'general',
    cover: '#e6a23c',
    doc_count: 0,
    total_size: 0,
    chunk_count: 0,
    last_test_at: null,
    created_at: '2026-07-20T09:15:00.000Z',
  }),
]

function document(
  id: string,
  name: string,
  status: DocumentAsset['status'],
  size: number,
  elementCount: number,
  metadata: Data,
  enabled = true
): Document {
  const ext = name.split('.').pop() || 'pdf'
  return withDocumentAliases({
    id,
    kb_id: 'kb1',
    name,
    ext,
    size,
    pages: 48,
    mode: id === 'doc2' ? 'fast' : 'precision',
    status,
    pct: status === 'done' ? 100 : status === 'parsing' ? 65 : 0,
    element_count: elementCount,
    chunk_count: 0,
    metadata,
    enabled,
    recall_count: 8,
    created_at: `2026-07-15T10:${id.slice(-1)}:00.000Z`,
  })
}

export const mockDocuments: DocumentAsset[] = [
  document(
    'doc1',
    '项目招标文件.pdf',
    'done',
    5_452_595,
    256,
    {
      document_name: '项目招标文件.pdf',
      file_size: 5_452_595,
      uploader: 'user1',
      upload_date: '2026-07-15',
      last_update_date: '2026-07-16',
      source: '招标平台',
      project: '智慧园区',
    }
  ),
  document(
    'doc2',
    '投标响应书.docx',
    'done',
    3_984_589,
    180,
    {
      document_name: '投标响应书.docx',
      file_size: 3_984_589,
      uploader: 'user1',
      upload_date: '2026-07-16',
      last_update_date: '2026-07-16',
      source: '内部编写',
      project: '智慧园区',
    },
    false
  ),
  document(
    'doc3',
    '评标报告.pdf',
    'parsing',
    2_174_976,
    0,
    {
      document_name: '评标报告.pdf',
      file_size: 2_174_976,
      uploader: 'user1',
      upload_date: '2026-07-17',
      last_update_date: '2026-07-17',
      source: '评标系统',
      project: '数据治理',
    }
  ),
]

function chunk(
  id: string,
  documentId: string,
  seq: number,
  content: string,
  clauseTitle: string,
  embeddingModel: string | null,
  metadata: Data,
  enabled = true
): ChunkAsset {
  const owner = mockDocuments.find((item) => item.id === documentId)
  return {
    id,
    kb_id: 'kb1',
    document_id: documentId,
    document_name: owner?.name || '',
    content,
    content_search: content.toLowerCase(),
    clause_title: clauseTitle,
    section_path: `第一章/${clauseTitle}`,
    page_number: seq + 1,
    seq,
    char_count: content.length,
    embedding_model: embeddingModel,
    metadata,
    enabled,
    recall_count: seq,
    created_at: `2026-07-18T09:0${seq}:00.000Z`,
  }
}

export const mockChunks: ChunkAsset[] = [
  chunk('chunk1', 'doc1', 1, '本项目需建设统一知识库，支持元数据筛选与混合检索。', '建设目标', 'bge-m3', { clause_type: '条款', effective_status: '现行', effective_date: '2026-01-01', priority: 'high' }),
  chunk('chunk2', 'doc1', 2, '投标人应提供系统架构说明、实施计划和验收方案。', '投标要求', 'bge-m3', { clause_type: '义务', effective_status: '现行', effective_date: '2026-01-01', priority: 'medium' }),
  chunk('chunk3', 'doc1', 3, '中标人负责数据迁移、系统部署和运维支持。', '服务范围', null, { clause_type: '义务', effective_status: '草案', effective_date: '2026-03-01', priority: 'low' }),
  chunk('chunk4', 'doc2', 4, '技术响应必须覆盖检索精度、响应时间和安全要求。', '技术响应', 'bge-m3', { clause_type: '条款', effective_status: '现行', effective_date: '2026-02-01', priority: 'high' }),
  chunk('chunk5', 'doc2', 5, '项目采用分阶段验收，每阶段输出验收报告。', '验收标准', null, { clause_type: '条款', effective_status: '待生效', effective_date: '2026-09-01', priority: 'medium' }),
  chunk('chunk6', 'doc2', 6, '违约责任按合同总额的千分之五执行。', '违约责任', 'bge-m3', { clause_type: '责任', effective_status: '现行', effective_date: '2026-02-01', priority: 'high' }),
  chunk('chunk7', 'doc3', 7, '评标委员会对技术方案、商务报价和服务能力评分。', '评标办法', 'bge-m3', { clause_type: '条款', effective_status: '现行', effective_date: '2026-04-01', priority: 'medium' }),
  chunk('chunk8', 'doc3', 8, '评分结果应记录评委意见并归档保存。', '结果归档', 'bge-m3', { clause_type: '义务', effective_status: '现行', effective_date: '2026-04-01', priority: 'low' }, false),
  chunk('chunk9', 'doc3', 9, '异议应在评分结果公示后三个工作日内提出。', '异议处理', null, { clause_type: '程序', effective_status: '现行', effective_date: '2026-04-01', priority: 'low' }),
]

const BUILT_IN_DOCUMENT_FIELD_KEYS = new Set([
  'document_name',
  'file_size',
  'uploader',
  'upload_date',
  'last_update_date',
  'source',
])

function field(
  id: string,
  key: string,
  name: string,
  scope: MetadataScope,
  dataType: MetadataDataType,
  sortOrder: number,
  mappedField: string | null = null,
  options: string[] = []
): MetadataField {
  return {
    id,
    kb_id: 'kb1',
    key,
    name,
    scope,
    data_type: dataType,
    options,
    default_value: null,
    required: false,
    filterable: mappedField !== null,
    retrieval_filterable: false,
    visible: true,
    built_in:
      scope === 'chunk' ||
      (scope === 'document' && BUILT_IN_DOCUMENT_FIELD_KEYS.has(key)),
    mapped_field: mappedField,
    sort_order: sortOrder,
  }
}

export const mockMetadataFields: MetadataField[] = [
  field('field-document-name', 'document_name', '文档名', 'document', 'string', 0, 'name'),
  field('field-file-size', 'file_size', '大小', 'document', 'number', 1, 'size'),
  field('field-uploader', 'uploader', '上传人', 'document', 'string', 2, 'user_id'),
  field('field-upload-date', 'upload_date', '上传时间', 'document', 'date', 3, 'created_at'),
  field('field-last-update', 'last_update_date', '更新时间', 'document', 'date', 4, 'updated_at'),
  field('field-source', 'source', '来源', 'document', 'string', 5),
  field('field-project', 'project', '项目', 'document', 'select', 6, null, ['智慧园区', '数据治理']),
  field('field-clause-type', 'clause_type', '条款类型', 'chunk', 'select', 7, null, ['条款', '义务', '责任', '程序']),
  field('field-effective-status', 'effective_status', '生效状态', 'chunk', 'select', 8, null, ['现行', '待生效', '草案']),
  field('field-effective-date', 'effective_date', '生效日期', 'chunk', 'date', 9),
  field('field-priority', 'priority', '优先级', 'chunk', 'string', 10),
]

mockMetadataFields.forEach((item) => {
  if (item.key === 'project') {
    item.built_in = false
    item.filterable = true
    item.retrieval_filterable = true
  }
  if (item.key === 'clause_type' || item.key === 'effective_status') {
    item.filterable = true
    item.retrieval_filterable = true
  }
})

function testSet(
  id: string,
  kbId: string,
  name: string,
  archived: boolean,
  caseCount: number
): RetrievalTestSet {
  return {
    id,
    kb_id: kbId,
    name,
    description: null,
    archived,
    case_count: caseCount,
    last_run_at: archived ? '2026-08-18T08:00:00.000Z' : '2026-08-20T09:30:00.000Z',
    last_metrics: {
      hit_at_k: { '1': 0.8, '3': 0.9, '5': 0.9 },
      recall_at_k: { '3': 0.78, '5': 0.86 },
    },
    created_at: '2026-08-01T08:00:00.000Z',
    updated_at: '2026-08-20T09:30:00.000Z',
  }
}

export const mockTestSets: RetrievalTestSet[] = [
  testSet('set-active', 'kb1', '招标检索基线', false, 5),
  testSet('set-archived', 'kb2', '合同验收回归', true, 1),
]

function testCase(
  id: string,
  setId: string,
  query: string,
  expectedDocs: string[],
  expectedChunks: string[],
  tags: string[],
  enabled: boolean,
  sortOrder: number
): RetrievalTestCase {
  return {
    id,
    test_set_id: setId,
    query,
    expected_doc_ids: expectedDocs,
    expected_chunk_ids: expectedChunks,
    tags,
    enabled,
    sort_order: sortOrder,
    created_at: '2026-08-02T08:00:00.000Z',
    updated_at: '2026-08-02T08:00:00.000Z',
  }
}

export const mockTestCases: RetrievalTestCase[] = [
  testCase('case1', 'set-active', '知识库支持哪些检索能力', ['doc1'], ['chunk1'], ['核心', '检索'], true, 1),
  testCase('case2', 'set-active', '投标人需要提交什么材料', ['doc2'], ['chunk4'], ['投标'], true, 2),
  testCase('case3', 'set-active', '项目验收流程是什么', ['doc1', 'doc2'], [], ['验收'], true, 3),
  testCase('case4', 'set-active', '系统安全要求汇总', [], [], ['巡检'], true, 4),
  testCase('case5', 'set-active', '评分结果如何归档', ['doc3'], ['chunk8'], ['评标'], false, 5),
  testCase('case6', 'set-archived', '合同违约责任', ['doc2'], ['chunk6'], ['合同'], true, 1),
]

const defaultSettings: RetrievalSettings = {
  values: {
    method: { value: 'hybrid', source: 'system_default' },
    final_top_k: { value: 5, source: 'system_default' },
    vector_top_k: { value: 20, source: 'system_default' },
    keyword_top_k: { value: 20, source: 'system_default' },
    vector_weight: { value: 0.7, source: 'system_default' },
    keyword_weight: { value: 0.3, source: 'system_default' },
    rerank_enabled: { value: true, source: 'system_default' },
    rerank_top_n: { value: 10, source: 'system_default' },
  },
  resolved: {
    method: 'hybrid',
    final_top_k: 5,
    vector_top_k: 20,
    keyword_top_k: 20,
    vector_weight: 0.7,
    keyword_weight: 0.3,
    rerank_enabled: true,
    rerank_top_n: 10,
  },
  embedding_model: {
    id: 'model-embedding',
    name: 'BGE-M3',
    prov: 'local',
    params: { dim: 1024 },
  },
  rerank_model: { id: 'model-rerank', name: 'BGE-Reranker', prov: 'local' },
  rebuild_required: false,
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function candidate(rank: number, chunkId: string, score: number): RetrievalCandidate {
  const source = mockChunks.find((item) => item.id === chunkId) || mockChunks[0]
  return {
    rank,
    chunk_id: source.id,
    document_id: source.document_id,
    document_name: source.document_name,
    section_path: source.section_path,
    page_number: source.page_number,
    char_count: source.char_count,
    vector_score: score,
    keyword_score: 1 - score,
    vector_rank: rank,
    keyword_rank: rank + 1,
    rrf_score: 1 / (60 + rank),
    rerank_score: 1 - rank * 0.08,
    metadata: { ...source.metadata },
  }
}

function completedRun(): RetrievalTestRun {
  return {
    id: 'run-completed',
    test_set_id: 'set-active',
    kb_id: 'kb1',
    status: 'completed',
    config_snapshot: {
      settings: cloneJson(defaultSettings),
      ks: [3, 5],
      embedding_model: { id: 'model-embedding', name: 'BGE-M3', prov: 'local', dim: 1024 },
      rerank_model: { id: 'model-rerank', name: 'BGE-Reranker', prov: 'local' },
      document_metadata: {},
      chunk_metadata: {},
    },
    override_config: { method: 'hybrid' },
    total_cases: 4,
    completed_cases: 4,
    metrics: {
      hit_at_k: { '1': 0.75, '3': 1.0, '5': 1.0 },
      recall_at_k: { '3': 0.82, '5': 0.9 },
      rerank_trigger_rate: 1.0,
      navigation_scoped_rate: 0.0,
      failure_rate: 0.0,
    },
    error: null,
    started_at: '2026-08-20T09:30:00.000Z',
    finished_at: '2026-08-20T09:30:18.000Z',
    created_at: '2026-08-20T09:30:00.000Z',
  }
}

export const mockTestRuns: RetrievalTestRun[] = [
  completedRun(),
  {
    id: 'run-canceled',
    test_set_id: 'set-active',
    kb_id: 'kb1',
    status: 'canceled',
    config_snapshot: {
      settings: cloneJson(defaultSettings),
      ks: [3],
      embedding_model: null,
      rerank_model: null,
      document_metadata: {},
      chunk_metadata: {},
    },
    override_config: {},
    total_cases: 2,
    completed_cases: 2,
    metrics: {},
    error: null,
    started_at: '2026-08-21T08:00:00.000Z',
    finished_at: '2026-08-21T08:00:05.000Z',
    created_at: '2026-08-21T08:00:00.000Z',
  },
]

function runResult(
  id: string,
  runId: string,
  sourceCase: RetrievalTestCase,
  status: RetrievalTestCaseResult['status'],
  resultChunks: string[]
): RetrievalTestCaseResult {
  const results = resultChunks.map((chunkId, index) => candidate(index + 1, chunkId, 0.95 - index * 0.08))
  const hitDocIds = Array.from(new Set(results.map((item) => item.document_id)))
    .filter((id) => sourceCase.expected_doc_ids.includes(id))
  return {
    ...sourceCase,
    id,
    run_id: runId,
    status,
    first_expected_hit_rank: hitDocIds.length ? results.findIndex((item) => item.document_id === hitDocIds[0]) + 1 : null,
    latency_ms: 80 + sourceCase.sort_order * 35,
    last_run_at: '2026-08-20T09:30:10.000Z',
    hit_doc_ids: hitDocIds,
    results,
    metrics: {
      hit_at_3: hitDocIds.length > 0 ? 1 : 0,
      recall_at_3: sourceCase.expected_doc_ids.length ? hitDocIds.length / sourceCase.expected_doc_ids.length : null,
      reciprocal_rank: hitDocIds.length ? 1 / (results.findIndex((item) => item.document_id === hitDocIds[0]) + 1) : 0,
    },
    error: null,
  }
}

export const mockTestCaseResults: RetrievalTestCaseResult[] = [
  runResult('result-completed-1', 'run-completed', mockTestCases[0], 'hit', ['chunk1', 'chunk4', 'chunk2']),
  runResult('result-completed-2', 'run-completed', mockTestCases[1], 'hit', ['chunk4', 'chunk6', 'chunk1']),
  runResult('result-completed-3', 'run-completed', mockTestCases[2], 'partial_hit', ['chunk5', 'chunk1', 'chunk4']),
  runResult('result-completed-4', 'run-completed', mockTestCases[3], 'skipped', []),
  { ...runResult('result-canceled-1', 'run-canceled', mockTestCases[0], 'skipped', []), results: [], hit_doc_ids: [], metrics: {} },
  { ...runResult('result-canceled-2', 'run-canceled', mockTestCases[1], 'skipped', []), results: [], hit_doc_ids: [], metrics: {} },
]

for (const documentItem of mockDocuments) {
  documentItem.chunk_count = mockChunks.filter((item) => item.document_id === documentItem.id).length
}

export const mockTree = [
  {
    node_id: 'n1',
    title: '第一章 项目概述',
    level: 1,
    summary: '项目背景和目标说明',
    element_count: 12,
    children: [
      { node_id: 'n1-1', title: '1.1 项目背景', level: 2, element_count: 5, children: [] },
      { node_id: 'n1-2', title: '1.2 项目目标', level: 2, element_count: 7, children: [] },
    ],
  },
  {
    node_id: 'n2',
    title: '第二章 技术方案',
    level: 1,
    summary: '系统架构和技术实现方案',
    element_count: 28,
    children: [
      { node_id: 'n2-1', title: '2.1 系统架构', level: 2, element_count: 10, children: [] },
      { node_id: 'n2-2', title: '2.2 技术选型', level: 2, element_count: 18, children: [] },
    ],
  },
]

export const mockElements = [
  {
    element_id: 'e1',
    doc_title: '项目招标文件.pdf',
    type: 'text' as const,
    content: '本项目旨在建设智能化的知识管理系统，实现知识沉淀、共享和应用。',
    node_id: 'n1-1',
    node_title: '1.1 项目背景',
    page_number: 1,
    seq: 1,
  },
  {
    element_id: 'e2',
    doc_title: '项目招标文件.pdf',
    type: 'table' as const,
    content: JSON.stringify({ headers: ['模块', '说明'], rows: [['检索', '支持元数据筛选']] }),
    node_id: 'n1-1',
    node_title: '1.1 项目背景',
    page_number: 2,
    seq: 2,
  },
  {
    element_id: 'e3',
    doc_title: '项目招标文件.pdf',
    type: 'heading' as const,
    content: '1.2 项目目标',
    node_id: 'n1-2',
    node_title: '1.2 项目目标',
    page_number: 3,
    seq: 1,
  },
]

export const mockParseTask = {
  task_id: 'task1',
  doc_id: 'doc3',
  status: 'parsing' as const,
  pct: 65,
}

function splitUrl(url: string): { path: string; query: URLLikeQuery } {
  const [rawPath, rawQuery = ''] = url.split('?')
  const query: URLLikeQuery = {}
  for (const pair of rawQuery.split('&')) {
    if (!pair) continue
    const equalIndex = pair.indexOf('=')
    const key = decodeURIComponent(pair.slice(0, equalIndex))
    const value = equalIndex === -1 ? '' : decodeURIComponent(pair.slice(equalIndex + 1))
    query[key] = value
  }
  return { path: rawPath.replace(/^\/?api\/v2\//, '').replace(/\/$/, ''), query }
}

interface URLLikeQuery {
  [key: string]: string
}

function parseJsonQuery(query: URLLikeQuery, key: string): Data {
  const raw = query[key]
  if (!raw) return {}
  try {
    const parsed: unknown = JSON.parse(raw)
    return isRecord(parsed) ? parsed : {}
  } catch {
    return {}
  }
}

function metadataMatches(metadata: Data, filters: Data): boolean {
  return Object.entries(filters).every(([key, expected]) => {
    const actual = metadata[key]
    if (Array.isArray(expected)) return expected.includes(actual)
    return actual === expected
  })
}

function paginate<T>(items: T[], query: URLLikeQuery): { list: T[]; total: number } {
  const page = Math.max(1, Number.parseInt(query.page || '1', 10))
  const pageSize = Math.min(100, Math.max(1, Number.parseInt(query.page_size || query.pageSize || '20', 10)))
  const start = (page - 1) * pageSize
  return { list: items.slice(start, start + pageSize), total: items.length }
}

function syncKb(kbId: string): void {
  const kb = mockKbs.find((item) => item.id === kbId)
  if (!kb) return
  const docs = mockDocuments.filter((item) => item.kb_id === kbId)
  kb.doc_count = docs.length
  kb.total_size = docs.reduce((sum, item) => sum + item.size, 0)
  kb.chunk_count = mockChunks.filter((item) => item.kb_id === kbId).length
  Object.assign(kb, withKbAliases(kb))
}

function syncTestSet(setId: string): void {
  const set = mockTestSets.find((item) => item.id === setId)
  if (!set) return
  set.case_count = mockTestCases.filter((item) => item.test_set_id === setId).length
  const latest = mockTestRuns
    .filter((item) => item.test_set_id === setId)
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
  set.last_run_at = latest?.created_at || null
  set.updated_at = nextTime()
}

function validateMetadataValue(fieldDefinition: MetadataField, value: unknown): string | null {
  if (fieldDefinition.data_type === 'string' && typeof value !== 'string') return `字段 ${fieldDefinition.key} 必须是字符串`
  if (fieldDefinition.data_type === 'number' && (typeof value !== 'number' || !Number.isFinite(value))) return `字段 ${fieldDefinition.key} 必须是数字`
  if (fieldDefinition.data_type === 'boolean' && typeof value !== 'boolean') return `字段 ${fieldDefinition.key} 必须是布尔值`
  if (fieldDefinition.data_type === 'date' && (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value))) return `字段 ${fieldDefinition.key} 必须是日期`
  if (fieldDefinition.data_type === 'select' && (typeof value !== 'string' || !fieldDefinition.options.includes(value))) return `字段 ${fieldDefinition.key} 不在选项内`
  return null
}

function cleanMetadata(
  kbId: string,
  scope: MetadataScope,
  metadata: Data,
  requireComplete: boolean
): Data | Envelope {
  const fields = mockMetadataFields.filter((item) => item.kb_id === kbId && item.scope === scope)
  const unknownKeys = Object.keys(metadata).filter((key) => !fields.some((item) => item.key === key))
  if (unknownKeys.length) return invalid(`未知元数据字段: ${unknownKeys.join(', ')}`)
  if (requireComplete) {
    const missing = fields.filter((item) => item.required && !(item.key in metadata))
    if (missing.length) return invalid(`必填元数据字段: ${missing.map((item) => item.key).join(', ')}`)
  }
  for (const [key, value] of Object.entries(metadata)) {
    const fieldDefinition = fields.find((item) => item.key === key)
    if (!fieldDefinition) continue
    if (fieldDefinition.mapped_field && fieldDefinition.key !== 'source') continue
    if (value === null) {
      if (fieldDefinition.required) return invalid(`字段 ${key} 不能为空`)
      continue
    }
    const error = validateMetadataValue(fieldDefinition, value)
    if (error) return invalid(error)
  }
  return { ...metadata }
}

function createFieldPayload(kbId: string, data: Data): MetadataField | Envelope {
  const key = text(data.key)
  const scope = text(data.scope) === 'chunk' ? 'chunk' : 'document'
  const dataType = text(data.data_type) as MetadataDataType
  const allowedTypes: MetadataDataType[] = ['string', 'number', 'date', 'select', 'boolean']
  if (!/^[a-z][a-z0-9_]{0,63}$/.test(key)) return invalid('字段标识格式不正确')
  if (!allowedTypes.includes(dataType)) return invalid('不支持的字段类型')
  if (mockMetadataFields.some((item) => item.kb_id === kbId && item.scope === scope && item.key === key)) {
    return invalid('字段标识已存在')
  }
  const options = stringList(data.options)
  if (dataType === 'select' && (!options.length || new Set(options).size !== options.length)) {
    return invalid('单选字段选项必须为非空且不重复的字符串列表')
  }
  if (dataType !== 'select' && options.length) return invalid('仅单选字段可以配置选项')
  const created: MetadataField = {
    id: nextId('field-'),
    kb_id: kbId,
    key,
    name: text(data.name) || key,
    scope,
    data_type: dataType,
    options,
    default_value: data.default_value ?? null,
    required: booleanValue(data.required),
    filterable: booleanValue(data.filterable),
    retrieval_filterable: booleanValue(data.retrieval_filterable),
    visible: booleanValue(data.visible, true),
    built_in: false,
    mapped_field: null,
    sort_order: numberValue(data.sort_order),
  }
  if (created.default_value !== null) {
    const error = validateMetadataValue(created, created.default_value)
    if (error) return invalid(error)
  }
  mockMetadataFields.push(created)
  return created
}

function aggregateMetrics(results: RetrievalTestCaseResult[], ks: number[]): RetrievalTestRun['metrics'] {
  const executed = results.filter((item) => item.status !== 'failed' && item.status !== 'pending' && item.status !== 'running')
  const hitAtK: Record<string, number | null> = {}
  const recallAtK: Record<string, number | null> = {}
  for (const k of ks) {
    const scored = executed.filter((item) => item.expected_doc_ids.length > 0)
    hitAtK[String(k)] = scored.length
      ? scored.filter((item) => item.results.slice(0, k).some((candidate) => item.expected_doc_ids.includes(candidate.document_id))).length / scored.length
      : null
    recallAtK[String(k)] = scored.length
      ? scored.reduce((sum, item) => {
          const hit = new Set(item.results.slice(0, k).filter((c) => item.expected_doc_ids.includes(c.document_id)).map((c) => c.document_id))
          return sum + hit.size / item.expected_doc_ids.length
        }, 0) / scored.length
      : null
  }
  return {
    hit_at_k: hitAtK,
    recall_at_k: recallAtK,
    rerank_trigger_rate: executed.length ? 1 : 0,
    navigation_scoped_rate: 0,
    failure_rate: results.length ? results.filter((item) => item.status === 'failed').length / results.length : 0,
  }
}

function advanceRun(run: RetrievalTestRun): void {
  if (run.status === 'pending') {
    run.status = 'running'
    run.started_at = nextTime()
  }
  if (run.status !== 'running') return
  const pending = mockTestCaseResults.find((item) => item.run_id === run.id && item.status === 'pending')
  if (pending) {
    const candidates = pending.query.includes('验收')
      ? ['chunk5', 'chunk1', 'chunk4']
      : pending.query.includes('投标人')
        ? ['chunk4', 'chunk6', 'chunk1']
        : ['chunk1', 'chunk4', 'chunk2']
    pending.results = candidates.map((chunkId, index) => candidate(index + 1, chunkId, 0.96 - index * 0.09))
    pending.hit_doc_ids = Array.from(new Set(pending.results.map((item) => item.document_id)))
      .filter((id) => pending.expected_doc_ids.includes(id))
    pending.status = pending.expected_doc_ids.length === 0
      ? 'skipped'
      : pending.expected_doc_ids.every((id) => pending.hit_doc_ids.includes(id))
        ? 'hit'
        : pending.hit_doc_ids.length
          ? 'partial_hit'
          : 'miss'
    pending.latency_ms = 75 + pending.sort_order * 27
    pending.last_run_at = nextTime()
    pending.metrics = {
      hit_at_3: pending.hit_doc_ids.length ? 1 : 0,
      recall_at_3: pending.expected_doc_ids.length ? pending.hit_doc_ids.length / pending.expected_doc_ids.length : null,
    }
    run.completed_cases += 1
  }
  if (run.completed_cases >= run.total_cases) {
    run.status = 'completed'
    run.finished_at = nextTime()
    run.metrics = aggregateMetrics(
      mockTestCaseResults.filter((item) => item.run_id === run.id),
      run.config_snapshot.ks
    )
  }
}

export function handleKnowledgeMock(
  url: string,
  method: string,
  data: Record<string, unknown>
): unknown | null {
  const { path, query } = splitUrl(url)
  const upperMethod = method.toUpperCase()

  let match: RegExpMatchArray | null

  // Metadata fields are matched before every broad /knowledge route.
  match = path.match(/^\/knowledge\/([^/]+)\/metadata-fields(?:\/([^/]+))?$/)
  if (match) {
    const kbId = match[1]
    const fieldId = match[2] || ''
    if (!mockKbs.some((item) => item.id === kbId)) return notFound('知识库不存在')
    if (upperMethod === 'GET') {
      const scope = query.scope as MetadataScope | undefined
      const fields = mockMetadataFields
        .filter((item) => item.kb_id === kbId && (!scope || item.scope === scope))
        .sort((a, b) => a.sort_order - b.sort_order)
      return ok(fields)
    }
    if (upperMethod === 'POST') {
      const result = createFieldPayload(kbId, data)
      return isEnvelope(result) ? result : ok(result)
    }
    if (upperMethod === 'PUT' && fieldId) {
      const fieldDefinition = mockMetadataFields.find((item) => item.id === fieldId && item.kb_id === kbId)
      if (!fieldDefinition) return notFound('字段不存在')
      if ('key' in data || 'scope' in data || 'data_type' in data) return invalid('字段标识、作用域和类型不可修改')
      if (typeof data.name === 'string' && data.name) fieldDefinition.name = data.name
      if (Array.isArray(data.options)) fieldDefinition.options = stringList(data.options)
      if ('default_value' in data) fieldDefinition.default_value = data.default_value ?? null
      if (typeof data.required === 'boolean' && !fieldDefinition.built_in) fieldDefinition.required = data.required
      if (typeof data.filterable === 'boolean') fieldDefinition.filterable = data.filterable
      if (typeof data.retrieval_filterable === 'boolean') fieldDefinition.retrieval_filterable = data.retrieval_filterable
      if (typeof data.visible === 'boolean') fieldDefinition.visible = data.visible
      if (typeof data.sort_order === 'number') fieldDefinition.sort_order = data.sort_order
      return ok(fieldDefinition)
    }
    if (upperMethod === 'DELETE' && fieldId) {
      const index = mockMetadataFields.findIndex((item) => item.id === fieldId && item.kb_id === kbId)
      if (index === -1) return notFound('字段不存在')
      const fieldDefinition = mockMetadataFields[index]
      if (fieldDefinition.built_in) return invalid('内置字段不可删除')
      const assets = fieldDefinition.scope === 'document' ? mockDocuments : mockChunks
      const affected = assets.filter((item) => fieldDefinition.key in item.metadata).length
      if (affected > 0 && query.force !== 'true') {
        return ok({ success: false, affected_count: affected })
      }
      assets.forEach((item) => {
        const metadata = { ...item.metadata }
        delete metadata[fieldDefinition.key]
        item.metadata = metadata
      })
      mockMetadataFields.splice(index, 1)
      return ok({ success: true, affected_count: affected })
    }
  }

  match = path.match(/^\/knowledge\/([^/]+)\/retrieval-settings$/)
  if (match) {
    const kbId = match[1]
    if (!mockKbs.some((item) => item.id === kbId)) return notFound('知识库不存在')
    if (upperMethod === 'GET') return ok(defaultSettings)
    if (upperMethod === 'PUT') {
      const config = isRecord(data.retrieval_config) ? data.retrieval_config : {}
      for (const [key, value] of Object.entries(config)) {
        if (!(key in defaultSettings.resolved)) return invalid(`未知检索配置: ${key}`)
        defaultSettings.values[key] = { value: value as string | number | boolean, source: 'override' }
        defaultSettings.resolved[key] = value as string | number | boolean
      }
      return ok(defaultSettings)
    }
  }

  match = path.match(/^\/knowledge\/([^/]+)\/retrieval-test-sets$/)
  if (match && upperMethod === 'GET') {
    const includeArchived = query.include_archived === 'true'
    const sets = mockTestSets.filter((item) => item.kb_id === match![1] && (includeArchived || !item.archived))
    return ok(paginate(sets, query))
  }
  if (match && upperMethod === 'POST') {
    const set: RetrievalTestSet = {
      id: nextId('set-'),
      kb_id: match[1],
      name: text(data.name),
      description: optionalText(data.description),
      archived: false,
      case_count: 0,
      last_run_at: null,
      last_metrics: null,
      created_at: nextTime(),
      updated_at: nextTime(),
    }
    mockTestSets.unshift(set)
    return ok(set)
  }

  // Standalone test-set and run routes must precede generic /knowledge matching.
  match = path.match(/^\/retrieval-test-sets\/([^/]+)\/cases$/)
  if (match && upperMethod === 'GET') {
    const cases = mockTestCases.filter((item) => item.test_set_id === match![1])
    const enabled = query.enabled
    const filtered = enabled === undefined ? cases : cases.filter((item) => item.enabled === (enabled === 'true'))
    const keyword = query.keyword || ''
    const tag = query.tag || ''
    return ok(paginate(filtered.filter((item) =>
      (!keyword || item.query.includes(keyword)) && (!tag || item.tags.includes(tag))
    ), query))
  }
  if (match && upperMethod === 'POST') {
    const source = mockTestCases.find((item) => item.test_set_id === match![1]) || mockTestCases[0]
    const created: RetrievalTestCase = {
      id: nextId('case-'),
      test_set_id: match[1],
      query: text(data.query),
      expected_doc_ids: stringList(data.expected_doc_ids),
      expected_chunk_ids: stringList(data.expected_chunk_ids),
      tags: stringList(data.tags),
      enabled: booleanValue(data.enabled, true),
      sort_order: numberValue(data.sort_order),
      created_at: nextTime(),
      updated_at: nextTime(),
    }
    if (!created.query) return invalid('query 不能为空')
    mockTestCases.push(created)
    syncTestSet(created.test_set_id)
    void source
    return ok(created)
  }

  match = path.match(/^\/retrieval-test-sets\/([^/]+)\/runs$/)
  if (match && upperMethod === 'GET') {
    return ok(paginate(mockTestRuns.filter((item) => item.test_set_id === match![1]), query))
  }
  if (match && upperMethod === 'POST') {
    const setId = match[1]
    const active = mockTestRuns.find((item) => item.test_set_id === setId && (item.status === 'pending' || item.status === 'running'))
    if (active) return ok(active)
    const requestedIds = stringList(data.case_ids)
    const cases = mockTestCases
      .filter((item) => item.test_set_id === setId && item.enabled && (!requestedIds.length || requestedIds.includes(item.id)))
      .sort((a, b) => a.sort_order - b.sort_order)
    if (!cases.length) return invalid('没有可执行的启用用例')
    const run: RetrievalTestRun = {
      id: nextId('run-'),
      test_set_id: setId,
      kb_id: mockTestSets.find((item) => item.id === setId)?.kb_id || 'kb1',
      status: 'pending',
      config_snapshot: {
        settings: cloneJson(defaultSettings),
        ks: numberList(data.ks),
        embedding_model: { id: 'model-embedding', name: 'BGE-M3', prov: 'local', dim: 1024 },
        rerank_model: cloneJson(defaultSettings.rerank_model),
        document_metadata: isRecord(data.document_metadata) ? data.document_metadata : {},
        chunk_metadata: isRecord(data.chunk_metadata) ? data.chunk_metadata : {},
      },
      override_config: isRecord(data.override_config) ? data.override_config : {},
      total_cases: cases.length,
      completed_cases: 0,
      metrics: {},
      error: null,
      started_at: null,
      finished_at: null,
      created_at: nextTime(),
    }
    if (!run.config_snapshot.ks.length) run.config_snapshot.ks = [3, 5]
    mockTestRuns.unshift(run)
    cases.forEach((sourceCase, index) => {
      mockTestCaseResults.push({
        ...sourceCase,
        id: nextId('result-'),
        run_id: run.id,
        status: 'pending',
        first_expected_hit_rank: null,
        latency_ms: null,
        last_run_at: null,
        hit_doc_ids: [],
        results: [],
        metrics: {},
        error: null,
        sort_order: index + 1,
      })
    })
    syncTestSet(setId)
    return ok(run)
  }

  match = path.match(/^\/retrieval-test-runs\/([^/]+)\/cases$/)
  if (match && upperMethod === 'GET') {
    return ok(paginate(mockTestCaseResults.filter((item) => item.run_id === match![1]), query))
  }

  match = path.match(/^\/retrieval-test-runs\/([^/]+)\/cancel$/)
  if (match && upperMethod === 'POST') {
    const run = mockTestRuns.find((item) => item.id === match![1])
    if (!run) return notFound('测试运行不存在')
    if (run.status === 'pending' || run.status === 'running') {
      mockTestCaseResults
        .filter((item) => item.run_id === run.id && (item.status === 'pending' || item.status === 'running'))
        .forEach((item) => {
          item.status = 'skipped'
          item.error = null
        })
      run.status = 'canceled'
      run.completed_cases = run.total_cases
      run.finished_at = nextTime()
    }
    return ok(run)
  }

  match = path.match(/^\/retrieval-test-runs\/([^/]+)$/)
  if (match && upperMethod === 'GET') {
    const run = mockTestRuns.find((item) => item.id === match![1])
    if (!run) return notFound('测试运行不存在')
    advanceRun(run)
    syncTestSet(run.test_set_id)
    return ok(run)
  }

  match = path.match(/^\/retrieval-test-sets\/([^/]+)$/)
  if (match) {
    const set = mockTestSets.find((item) => item.id === match![1])
    if (!set) return notFound('测试集不存在')
    if (upperMethod === 'GET') return ok(set)
    if (upperMethod === 'PUT') {
      if (typeof data.name === 'string' && data.name) set.name = data.name
      if ('description' in data) set.description = optionalText(data.description)
      if (typeof data.archived === 'boolean') set.archived = data.archived
      set.updated_at = nextTime()
      return ok(set)
    }
    if (upperMethod === 'DELETE') {
      const runIds = mockTestRuns.filter((item) => item.test_set_id === set.id).map((item) => item.id)
      removeInPlace(mockTestCaseResults, (item) => runIds.includes(item.run_id))
      removeInPlace(mockTestRuns, (item) => item.test_set_id === set.id)
      removeInPlace(mockTestCases, (item) => item.test_set_id === set.id)
      removeInPlace(mockTestSets, (item) => item.id === set.id)
      return ok({ success: true })
    }
  }

  match = path.match(/^\/retrieval-test-cases\/batch-status$/)
  if (match && upperMethod === 'POST') {
    const ids = stringList(data.ids)
    const enabled = booleanValue(data.enabled, true)
    const updated = mockTestCases.filter((item) => ids.includes(item.id))
    updated.forEach((item) => {
      item.enabled = enabled
      item.updated_at = nextTime()
    })
    Array.from(new Set(updated.map((item) => item.test_set_id))).forEach(syncTestSet)
    return ok({ updated: updated.length })
  }

  match = path.match(/^\/retrieval-test-cases\/([^/]+)$/)
  if (match) {
    const testCaseItem = mockTestCases.find((item) => item.id === match![1])
    if (!testCaseItem) return notFound('测试用例不存在')
    if (upperMethod === 'PUT') {
      if (typeof data.query === 'string' && data.query) testCaseItem.query = data.query
      if (Array.isArray(data.expected_doc_ids)) testCaseItem.expected_doc_ids = stringList(data.expected_doc_ids)
      if (Array.isArray(data.expected_chunk_ids)) testCaseItem.expected_chunk_ids = stringList(data.expected_chunk_ids)
      if (Array.isArray(data.tags)) testCaseItem.tags = stringList(data.tags)
      if (typeof data.enabled === 'boolean') testCaseItem.enabled = data.enabled
      if (typeof data.sort_order === 'number') testCaseItem.sort_order = data.sort_order
      testCaseItem.updated_at = nextTime()
      syncTestSet(testCaseItem.test_set_id)
      return ok(testCaseItem)
    }
    if (upperMethod === 'DELETE') {
      removeInPlace(mockTestCases, (item) => item.id !== testCaseItem.id)
      syncTestSet(testCaseItem.test_set_id)
      return ok({ success: true })
    }
  }

  match = path.match(/^\/chunks\/reembed$/)
  if (match && upperMethod === 'POST') return ok({ queued: true })

  match = path.match(/^\/chunks\/batch-(metadata|status)$/)
  if (match && upperMethod === 'POST') {
    const ids = stringList(data.ids)
    const rows = mockChunks.filter((item) => ids.includes(item.id))
    if (match[1] === 'metadata') {
      const metadata = isRecord(data.metadata) ? data.metadata : {}
      const firstKb = rows[0]?.kb_id
      if (firstKb) {
        const cleaned = cleanMetadata(firstKb, 'chunk', metadata, false)
        if (isEnvelope(cleaned)) return cleaned
        rows.forEach((item) => {
          item.metadata = { ...item.metadata, ...cleaned }
        })
      }
      return ok({ updated: rows.length })
    }
    const enabled = booleanValue(data.enabled, true)
    rows.forEach((item) => {
      item.enabled = enabled
    })
    return ok({ updated: rows.length })
  }

  match = path.match(/^\/chunks\/([^/]+)\/metadata$/)
  if (match && upperMethod === 'PATCH') {
    const chunkItem = mockChunks.find((item) => item.id === match![1])
    if (!chunkItem) return notFound('分块不存在')
    const metadata = isRecord(data.metadata) ? data.metadata : {}
    const target = { ...chunkItem.metadata, ...metadata }
    const cleaned = cleanMetadata(chunkItem.kb_id, 'chunk', target, true)
    if (isEnvelope(cleaned)) return cleaned
    chunkItem.metadata = cleaned
    return ok(chunkItem)
  }

  if (path === '/chunks' && upperMethod === 'GET') {
    let rows = mockChunks.filter((item) => item.kb_id === query.kb_id)
    if (query.document_id) rows = rows.filter((item) => item.document_id === query.document_id)
    if (query.keyword) rows = rows.filter((item) => item.content.includes(query.keyword) || (item.clause_title || '').includes(query.keyword))
    if (query.enabled) rows = rows.filter((item) => item.enabled === (query.enabled === 'true'))
    if (query.vector_state === 'vectorized') rows = rows.filter((item) => item.embedding_model !== null)
    if (query.vector_state === 'pending') rows = rows.filter((item) => item.embedding_model === null)
    const filters = parseJsonQuery(query, 'chunk_metadata')
    if (Object.keys(filters).length) rows = rows.filter((item) => metadataMatches(item.metadata, filters))
    return ok(paginate(rows.sort((a, b) => a.seq - b.seq), query))
  }

  match = path.match(/^\/documents\/batch-(metadata|status)$/)
  if (match && upperMethod === 'POST') {
    const ids = stringList(data.ids)
    const rows = mockDocuments.filter((item) => ids.includes(item.id))
    if (match[1] === 'metadata') {
      const metadata = isRecord(data.metadata) ? data.metadata : {}
      const firstKb = rows[0]?.kb_id
      if (firstKb) {
        const cleaned = cleanMetadata(firstKb, 'document', metadata, false)
        if (isEnvelope(cleaned)) return cleaned
        rows.forEach((item) => {
          item.metadata = { ...item.metadata, ...cleaned }
        })
      }
      return ok({ updated: rows.length })
    }
    const enabled = booleanValue(data.enabled, true)
    rows.forEach((item) => {
      item.enabled = enabled
    })
    return ok({ updated: rows.length })
  }

  match = path.match(/^\/documents\/([^/]+)\/metadata$/)
  if (match && upperMethod === 'PATCH') {
    const doc = mockDocuments.find((item) => item.id === match![1])
    if (!doc) return notFound('文档不存在')
    const metadata = isRecord(data.metadata) ? data.metadata : {}
    const target = { ...doc.metadata, ...metadata }
    const cleaned = cleanMetadata(doc.kb_id, 'document', target, true)
    if (isEnvelope(cleaned)) return cleaned
    doc.metadata = cleaned
    Object.assign(doc, withDocumentAliases(doc))
    return ok(doc)
  }

  if (path === '/documents' && upperMethod === 'GET') {
    let rows = mockDocuments.filter((item) => item.kb_id === query.kb_id)
    if (query.keyword) rows = rows.filter((item) => item.name.includes(query.keyword))
    if (query.status) rows = rows.filter((item) => item.status === query.status)
    if (query.enabled) rows = rows.filter((item) => item.enabled === (query.enabled === 'true'))
    const filters = parseJsonQuery(query, 'document_metadata')
    if (Object.keys(filters).length) rows = rows.filter((item) => metadataMatches(item.metadata, filters))
    const sort = query.sort || 'created_desc'
    const sorted = [...rows].sort((a, b) => {
      if (sort === 'name_asc') return a.name.localeCompare(b.name)
      if (sort === 'name_desc') return b.name.localeCompare(a.name)
      if (sort === 'chunk_count_desc') return b.chunk_count - a.chunk_count
      if (sort === 'recall_count_desc') return b.recall_count - a.recall_count
      return b.created_at.localeCompare(a.created_at)
    })
    return ok(paginate(sorted, query))
  }

  match = path.match(/^\/documents\/([^/]+)$/)
  if (match && upperMethod === 'GET') {
    const doc = mockDocuments.find((item) => item.id === match![1])
    return doc ? ok(doc) : notFound('文档不存在')
  }
  if (match && upperMethod === 'DELETE') {
    removeInPlace(mockDocuments, (item) => item.id === match![1])
    removeInPlace(mockChunks, (item) => item.document_id === match![1])
    syncKb('kb1')
    return ok({ success: true })
  }

  // Legacy knowledge CRUD remains after all specialized knowledge routes.
  if (path === '/knowledge' && upperMethod === 'GET') {
    const keyword = query.keyword || ''
    return ok(mockKbs.filter((item) => !keyword || item.name.includes(keyword)))
  }
  if (path === '/knowledge' && upperMethod === 'POST') {
    const created: KnowledgeBase = {
      id: nextId('kb-'),
      name: text(data.name),
      description: data.description !== undefined ? optionalText(data.description) : optionalText(data.desc),
      desc: '',
      scene: text(data.scene, 'general'),
      cover: optionalText(data.cover),
      doc_count: 0,
      total_size: 0,
      chunk_count: 0,
      last_test_at: null,
      created_at: nextTime(),
    }
    mockKbs.push(withKbAliases(created))
    return ok(withKbAliases(created))
  }

  match = path.match(/^\/knowledge\/([^/]+)$/)
  if (match) {
    const kb = mockKbs.find((item) => item.id === match![1])
    if (!kb) return notFound('知识库不存在')
    if (upperMethod === 'GET') return ok(kb)
    if (upperMethod === 'PUT') {
      if (typeof data.name === 'string' && data.name) kb.name = data.name
      if ('description' in data) kb.description = optionalText(data.description)
      if ('desc' in data && !('description' in data)) kb.description = optionalText(data.desc)
      if (typeof data.scene === 'string') kb.scene = data.scene
      if ('cover' in data) kb.cover = optionalText(data.cover)
      Object.assign(kb, withKbAliases(kb))
      return ok(kb)
    }
    if (upperMethod === 'DELETE') {
      removeInPlace(mockKbs, (item) => item.id !== kb.id)
      removeInPlace(mockDocuments, (item) => item.kb_id !== kb.id)
      removeInPlace(mockChunks, (item) => item.kb_id !== kb.id)
      return ok({ success: true })
    }
  }

  if (path === '/documents/tree-cache') {
    return ok({ tree: mockTree, elements: mockElements, task: mockParseTask })
  }

  return null
}
