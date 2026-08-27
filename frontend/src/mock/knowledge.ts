// 知识库 Mock 数据
import type {
  KnowledgeBase, Document, TreeNode, DocElement, ParseTask,
  RetrievalSettings, MetadataField, Segment, HitTestRecord, HitTestResult,
  RetrievalTestSet, RetrievalTestCase, RetrievalTestRun
} from '@/types/knowledge'

// Mock 知识库列表
export const mockKnowledgeBases: KnowledgeBase[] = [
  {
    id: 'kb1',
    name: '标书知识库',
    desc: '招投标相关文档，包括招标文件、投标文件、评标报告等',
    scene: 'bidding',
    docCount: 12,
    totalSize: '45.6 MB',
    createdAt: '2026-07-15 10:30:00',
    cover: '#409eff',
    embeddingModel: 'text-embedding-v3',
    rerankModel: 'gte-rerank-v2',
    chunkMethod: 'parent_child',
    segmentCount: 256,
    lastTestTime: '2026-08-20 15:30:00'
  },
  {
    id: 'kb2',
    name: '合同知识库',
    desc: '各类合同模板和已签署合同文档',
    scene: 'contract',
    docCount: 8,
    totalSize: '23.2 MB',
    createdAt: '2026-07-18 14:20:00',
    cover: '#67c23a',
    embeddingModel: 'text-embedding-v3',
    rerankModel: 'bge-reranker-v2-m3',
    chunkMethod: 'general',
    segmentCount: 45,
    lastTestTime: '2026-08-18 10:00:00'
  },
  {
    id: 'kb3',
    name: '通用知识库',
    desc: '公司通用文档、制度规范、操作手册等',
    scene: 'general',
    docCount: 15,
    totalSize: '89.4 MB',
    createdAt: '2026-07-20 09:15:00',
    cover: '#e6a23c',
    chunkMethod: 'general',
    segmentCount: 120
  }
]

// Mock 文档列表
export const mockDocuments: Document[] = [
  {
    id: 'doc1',
    kbId: 'kb1',
    name: '项目招标文件.pdf',
    ext: 'pdf',
    size: '5.2 MB',
    pages: 48,
    mode: 'precision',
    status: 'done',
    elementCount: 256,
    createdAt: '2026-07-15 11:00:00',
    enabled: true,
    recallCount: 18,
    charCount: 24500,
    segmentMode: 'parent_child',
    metadata: { source: '招标单位', author: '张三', date: '2026-07-10' }
  },
  {
    id: 'doc2',
    kbId: 'kb1',
    name: '投标响应书.docx',
    ext: 'docx',
    size: '3.8 MB',
    pages: 32,
    mode: 'fast',
    status: 'done',
    elementCount: 180,
    createdAt: '2026-07-16 09:30:00',
    enabled: true,
    recallCount: 12,
    charCount: 18500,
    segmentMode: 'general',
    metadata: { source: '投标单位', author: '李四' }
  },
  {
    id: 'doc3',
    kbId: 'kb1',
    name: '评标报告.pdf',
    ext: 'pdf',
    size: '2.1 MB',
    pages: 18,
    mode: 'precision',
    status: 'parsing',
    pct: 65,
    elementCount: 0,
    createdAt: '2026-07-17 14:20:00',
    enabled: false,
    recallCount: 0,
    charCount: 0,
    segmentMode: 'parent_child',
    metadata: {}
  },
  {
    id: 'doc4',
    kbId: 'kb2',
    name: '采购合同模板.docx',
    ext: 'docx',
    size: '1.5 MB',
    pages: 12,
    mode: 'fast',
    status: 'done',
    elementCount: 45,
    createdAt: '2026-07-18 15:00:00',
    enabled: true,
    recallCount: 5,
    charCount: 8200,
    segmentMode: 'general',
    metadata: { source: '法务部' }
  }
]

// ========== 检索设置（每知识库独立） ==========

export const mockRetrievalSettings: Record<string, RetrievalSettings> = {
  kb1: {
    embeddingModel: 'text-embedding-v3',
    rerankModel: 'gte-rerank-v2',
    chunkMethod: 'parent_child',
    chunkSize: 500,
    chunkOverlap: 50,
    config: {
      method: { value: 'hybrid', source: 'knowledge_base' },
      vectorTopK: { value: 10, source: 'knowledge_base' },
      keywordTopK: { value: 10, source: 'system_default' },
      similarityThreshold: { value: 0.5, source: 'knowledge_base' },
      similarityThresholdEnabled: { value: true, source: 'knowledge_base' },
      vectorWeight: { value: 0.7, source: 'knowledge_base' },
      keywordWeight: { value: 0.3, source: 'knowledge_base' },
      rrfK: { value: 60, source: 'system_default' },
      rerankEnabled: { value: true, source: 'knowledge_base' },
      rerankTopN: { value: 5, source: 'knowledge_base' },
      rerankTriggerThreshold: { value: 10, source: 'system_default' },
      navigationEnabled: { value: false, source: 'system_default' },
      navAnchorCount: { value: 3, source: 'system_default' },
      navConfidenceThreshold: { value: 0.8, source: 'system_default' }
    }
  },
  kb2: {
    embeddingModel: 'text-embedding-v3',
    rerankModel: 'bge-reranker-v2-m3',
    chunkMethod: 'general',
    chunkSize: 512,
    chunkOverlap: 50,
    config: {
      method: { value: 'vector', source: 'knowledge_base' },
      vectorTopK: { value: 5, source: 'system_default' },
      keywordTopK: { value: 5, source: 'system_default' },
      similarityThreshold: { value: 0.3, source: 'system_default' },
      similarityThresholdEnabled: { value: true, source: 'knowledge_base' },
      vectorWeight: { value: 0.8, source: 'system_default' },
      keywordWeight: { value: 0.2, source: 'system_default' },
      rrfK: { value: 60, source: 'system_default' },
      rerankEnabled: { value: false, source: 'knowledge_base' },
      rerankTopN: { value: 3, source: 'system_default' },
      rerankTriggerThreshold: { value: 10, source: 'system_default' },
      navigationEnabled: { value: false, source: 'system_default' },
      navAnchorCount: { value: 3, source: 'system_default' },
      navConfidenceThreshold: { value: 0.8, source: 'system_default' }
    }
  },
  kb3: {
    embeddingModel: 'text-embedding-v3',
    rerankModel: 'gte-rerank-v2',
    chunkMethod: 'general',
    chunkSize: 500,
    chunkOverlap: 50,
    config: {
      method: { value: 'hybrid', source: 'system_default' },
      vectorTopK: { value: 5, source: 'system_default' },
      keywordTopK: { value: 5, source: 'system_default' },
      similarityThreshold: { value: 0.3, source: 'system_default' },
      similarityThresholdEnabled: { value: false, source: 'system_default' },
      vectorWeight: { value: 0.7, source: 'system_default' },
      keywordWeight: { value: 0.3, source: 'system_default' },
      rrfK: { value: 60, source: 'system_default' },
      rerankEnabled: { value: true, source: 'system_default' },
      rerankTopN: { value: 5, source: 'system_default' },
      rerankTriggerThreshold: { value: 10, source: 'system_default' },
      navigationEnabled: { value: false, source: 'system_default' },
      navAnchorCount: { value: 3, source: 'system_default' },
      navConfidenceThreshold: { value: 0.8, source: 'system_default' }
    }
  }
}

// ========== 元数据字段定义 ==========

function buildBuiltInMetadataFields(kbId: string): MetadataField[] {
  return [
    { id: 'builtin-source', kbId, key: 'source', name: '来源', scope: 'document', dataType: 'string', options: [], required: false, filterable: true, retrievalFilterable: false, visible: true, builtIn: true, mappedField: 'doc_source', sortOrder: 1 },
    { id: 'builtin-author', kbId, key: 'author', name: '作者', scope: 'document', dataType: 'string', options: [], required: false, filterable: true, retrievalFilterable: false, visible: true, builtIn: true, mappedField: 'doc_author', sortOrder: 2 },
    { id: 'builtin-date', kbId, key: 'date', name: '创建日期', scope: 'document', dataType: 'date', options: [], required: false, filterable: true, retrievalFilterable: false, visible: true, builtIn: true, mappedField: 'doc_date', sortOrder: 3 },
    { id: 'builtin-doc_type', kbId, key: 'doc_type', name: '文档类型', scope: 'document', dataType: 'select', options: ['招标文件', '投标文件', '合同', '报告', '其他'], required: false, filterable: true, retrievalFilterable: true, visible: true, builtIn: true, sortOrder: 4 },
    { id: 'builtin-chunk_seq', kbId, key: 'chunk_seq', name: '分段序号', scope: 'chunk', dataType: 'number', options: [], required: false, filterable: false, retrievalFilterable: false, visible: true, builtIn: true, mappedField: 'chunk_seq', sortOrder: 5 },
    { id: 'builtin-chunk_type', kbId, key: 'chunk_type', name: '分段类型', scope: 'chunk', dataType: 'select', options: ['正文', '标题', '表格', '问答'], required: false, filterable: true, retrievalFilterable: true, visible: true, builtIn: true, sortOrder: 6 }
  ]
}

const customFields: MetadataField[] = [
  { id: 'cf1', kbId: 'kb1', key: 'project_name', name: '项目名称', scope: 'document', dataType: 'string', options: [], required: true, filterable: true, retrievalFilterable: true, visible: true, builtIn: false, sortOrder: 10 },
  { id: 'cf2', kbId: 'kb1', key: 'bid_amount', name: '投标金额(万元)', scope: 'document', dataType: 'number', options: [], required: false, filterable: true, retrievalFilterable: false, visible: true, builtIn: false, sortOrder: 11 },
  { id: 'cf3', kbId: 'kb1', key: 'section_type', name: '章节类型', scope: 'chunk', dataType: 'select', options: ['技术方案', '商务报价', '资质证明', '其他'], required: false, filterable: true, retrievalFilterable: true, visible: true, builtIn: false, sortOrder: 12 }
]

export const mockMetadataFields: Record<string, MetadataField[]> = {
  kb1: [...buildBuiltInMetadataFields('kb1'), ...customFields],
  kb2: [...buildBuiltInMetadataFields('kb2')],
  kb3: [...buildBuiltInMetadataFields('kb3')]
}

// ========== 分段数据 ==========

export const mockSegments: Record<string, Segment[]> = {
  kb1: [
    { id: 'seg1', docId: 'doc1', kbId: 'kb1', seq: 1, type: 'parent', content: '第一章 项目概述\n\n本项目旨在建设一个智能化的知识管理系统，实现知识的沉淀、共享和应用。系统需具备知识采集、知识组织、知识检索、知识推送等核心功能。项目预算为500万元，工期12个月。', charCount: 120, recallCount: 5, enabled: true, metadata: { section_type: '技术方案' }, children: [
      { id: 'seg1-1', docId: 'doc1', kbId: 'kb1', parentId: 'seg1', seq: 1, type: 'text', content: '1.1 项目背景：随着公司业务规模不断扩大，传统的文档管理方式已无法满足知识沉淀和共享的需求，亟需建设一套智能化的知识管理系统。', charCount: 65, recallCount: 3, enabled: true, metadata: {} },
      { id: 'seg1-2', docId: 'doc1', kbId: 'kb1', parentId: 'seg1', seq: 2, type: 'text', content: '1.2 项目目标：通过引入AI技术，实现文档自动解析、智能分块、语义检索和关联推荐，提升知识获取效率50%以上。', charCount: 58, recallCount: 2, enabled: true, metadata: {} }
    ]},
    { id: 'seg2', docId: 'doc1', kbId: 'kb1', seq: 2, type: 'parent', content: '第二章 技术方案\n\n系统采用微服务架构，前端Vue3 + 后端Python FastAPI，向量数据库使用Milvus，全文检索使用Elasticsearch。', charCount: 85, recallCount: 8, enabled: true, metadata: { section_type: '技术方案' }, children: [
      { id: 'seg2-1', docId: 'doc1', kbId: 'kb1', parentId: 'seg2', seq: 1, type: 'text', content: '2.1 系统架构：采用前后端分离的微服务架构，API网关统一入口，各服务独立部署和扩展。', charCount: 42, recallCount: 4, enabled: true, metadata: {} },
      { id: 'seg2-2', docId: 'doc1', kbId: 'kb1', parentId: 'seg2', seq: 2, type: 'text', content: '2.2 技术选型：向量数据库选用Milvus支持十亿级向量检索，全文检索使用Elasticsearch实现精确匹配。', charCount: 45, recallCount: 6, enabled: true, metadata: {} }
    ]},
    { id: 'seg3', docId: 'doc2', kbId: 'kb1', seq: 1, type: 'text', content: '投标响应书：我方已仔细阅读招标文件，完全理解项目需求，承诺按期完成项目建设。投标金额480万元。', charCount: 50, recallCount: 3, enabled: true, metadata: { section_type: '商务报价' } },
    { id: 'seg4', docId: 'doc2', kbId: 'kb1', seq: 2, type: 'text', content: '资质证明：我方具有CMMI3级认证、ISO9001质量管理体系认证，近三年完成类似项目15个。', charCount: 40, recallCount: 1, enabled: false, metadata: { section_type: '资质证明' } }
  ],
  kb2: [
    { id: 'seg5', docId: 'doc4', kbId: 'kb2', seq: 1, type: 'text', content: '采购合同\n\n甲方（采购方）：XX公司\n乙方（供应方）：XX供应商\n\n根据《中华人民共和国合同法》，双方就采购事宜达成如下协议。', charCount: 60, recallCount: 2, enabled: true, metadata: {} },
    { id: 'seg6', docId: 'doc4', kbId: 'kb2', seq: 2, type: 'text', content: '第一条 采购内容：乙方向甲方提供办公设备一批，包括台式电脑50台、笔记本电脑20台、打印机10台。', charCount: 45, recallCount: 1, enabled: true, metadata: {} },
    { id: 'seg7', docId: 'doc4', kbId: 'kb2', seq: 3, type: 'text', content: '第二条 付款方式：合同签订后7个工作日内支付30%预付款，验收合格后支付剩余70%。', charCount: 40, recallCount: 0, enabled: true, metadata: {} }
  ]
}

// ========== 召回测试（即时） ==========

export function createMockHitTestResult(query: string): HitTestResult {
  return {
    query,
    retrievalMode: 'hybrid',
    segments: [
      { id: 'seg2-1', docId: 'doc1', docName: '项目招标文件.pdf', content: '2.1 系统架构：采用前后端分离的微服务架构，API网关统一入口，各服务独立部署和扩展。', charCount: 42, score: 0.92, vectorScore: 0.88, keywordScore: 0.95, rerankScore: 0.92 },
      { id: 'seg2', docId: 'doc1', docName: '项目招标文件.pdf', content: '第二章 技术方案\n\n系统采用微服务架构，前端Vue3 + 后端Python FastAPI，向量数据库使用Milvus，全文检索使用Elasticsearch。', charCount: 85, score: 0.85, vectorScore: 0.82, keywordScore: 0.88, rerankScore: 0.85, children: [
        { id: 'seg2-1', docId: 'doc1', docName: '项目招标文件.pdf', content: '2.1 系统架构：采用前后端分离的微服务架构，API网关统一入口，各服务独立部署和扩展。', charCount: 42, score: 0.88, vectorScore: 0.85, keywordScore: 0.90, rerankScore: 0.88 },
        { id: 'seg2-2', docId: 'doc1', docName: '项目招标文件.pdf', content: '2.2 技术选型：向量数据库选用Milvus支持十亿级向量检索，全文检索使用Elasticsearch实现精确匹配。', charCount: 45, score: 0.78, vectorScore: 0.75, keywordScore: 0.80, rerankScore: 0.78 }
      ]},
      { id: 'seg1', docId: 'doc1', docName: '项目招标文件.pdf', content: '第一章 项目概述\n\n本项目旨在建设一个智能化的知识管理系统，实现知识的沉淀、共享和应用。系统需具备知识采集、知识组织、知识检索、知识推送等核心功能。项目预算为500万元，工期12个月。', charCount: 120, score: 0.71, vectorScore: 0.68, keywordScore: 0.75, rerankScore: 0.71, children: [
        { id: 'seg1-1', docId: 'doc1', docName: '项目招标文件.pdf', content: '1.1 项目背景：随着公司业务规模不断扩大，传统的文档管理方式已无法满足知识沉淀和共享的需求，亟需建设一套智能化的知识管理系统。', charCount: 65, score: 0.65, vectorScore: 0.62, keywordScore: 0.68, rerankScore: 0.65 }
      ]}
    ]
  }
}

export const mockHitTestRecords: HitTestRecord[] = [
  { id: 'hit1', kbId: 'kb1', query: '系统架构是什么', source: 'immediate', retrievalMode: 'hybrid', createdAt: '2026-08-20 15:30:00', result: createMockHitTestResult('系统架构是什么') },
  { id: 'hit2', kbId: 'kb1', query: '项目预算多少', source: 'immediate', retrievalMode: 'vector', createdAt: '2026-08-19 10:15:00' },
  { id: 'hit3', kbId: 'kb1', query: '投标金额', source: 'immediate', retrievalMode: 'hybrid', createdAt: '2026-08-18 14:00:00' }
]

// ========== 召回测试（批量） ==========

export const mockTestSets: RetrievalTestSet[] = [
  { id: 'ts1', kbId: 'kb1', name: '标书基础问答', description: '验证标书知识库的基础问答召回效果', caseCount: 3, lastRunTime: '2026-08-20 15:30:00', lastMetrics: { hitAtK: 0.89, recallAtK: 0.93, mrr: 0.82, p50Latency: 120, p95Latency: 280, rerankTriggerRate: 1.0, failureRate: 0.0 }, status: 'latest' },
  { id: 'ts2', kbId: 'kb1', name: '技术方案专项', description: '针对技术方案章节的召回测试', caseCount: 2, status: 'draft' }
]

export const mockTestCases: RetrievalTestCase[] = [
  { id: 'tc1', testSetId: 'ts1', query: '系统采用了什么架构', expectedDocIds: ['doc1'], expectedChunkIds: ['seg2', 'seg2-1'], tags: ['架构'], enabled: true, lastHitRank: 1, lastStatus: 'hit', lastLatency: 95 },
  { id: 'tc2', testSetId: 'ts1', query: '向量数据库用什么', expectedDocIds: ['doc1'], expectedChunkIds: ['seg2-2'], tags: ['技术选型'], enabled: true, lastHitRank: 2, lastStatus: 'hit', lastLatency: 110 },
  { id: 'tc3', testSetId: 'ts1', query: '项目预算是多少', expectedDocIds: ['doc1'], expectedChunkIds: ['seg1'], tags: ['预算'], enabled: true, lastHitRank: 3, lastStatus: 'partial_hit', lastLatency: 130 },
  { id: 'tc4', testSetId: 'ts2', query: '系统架构是怎样的', expectedDocIds: ['doc1'], expectedChunkIds: ['seg2-1'], tags: ['架构'], enabled: true },
  { id: 'tc5', testSetId: 'ts2', query: '项目目标是什么', expectedDocIds: ['doc1'], expectedChunkIds: ['seg1-2'], tags: ['目标'], enabled: true }
]

export const mockTestRuns: RetrievalTestRun[] = []

export function createMockTestRun(testSetId: string, kbId: string): RetrievalTestRun {
  const cases = mockTestCases.filter(tc => tc.testSetId === testSetId)
  return {
    id: 'run' + Date.now(),
    testSetId,
    kbId,
    status: 'completed',
    totalCases: cases.length,
    completedCases: cases.length,
    metrics: {
      hitAtK: 0.89,
      recallAtK: 0.93,
      mrr: 0.82,
      p50Latency: 120,
      p95Latency: 280,
      rerankTriggerRate: 1.0,
      failureRate: 0.0
    },
    startedAt: '2026-08-20 15:29:00',
    finishedAt: '2026-08-20 15:30:00',
    createdAt: '2026-08-20 15:30:00'
  }
}

// Mock 结构树
export const mockTree: TreeNode[] = [
  {
    node_id: 'n1',
    title: '第一章 项目概述',
    level: 1,
    summary: '项目背景和目标说明',
    element_count: 12,
    children: [
      {
        node_id: 'n1-1',
        title: '1.1 项目背景',
        level: 2,
        element_count: 5,
        children: []
      },
      {
        node_id: 'n1-2',
        title: '1.2 项目目标',
        level: 2,
        element_count: 7,
        children: []
      }
    ]
  },
  {
    node_id: 'n2',
    title: '第二章 技术方案',
    level: 1,
    summary: '系统架构和技术实现方案',
    element_count: 28,
    children: [
      {
        node_id: 'n2-1',
        title: '2.1 系统架构',
        level: 2,
        element_count: 10,
        children: []
      },
      {
        node_id: 'n2-2',
        title: '2.2 技术选型',
        level: 2,
        element_count: 18,
        children: []
      }
    ]
  },
  {
    node_id: 'n3',
    title: '第三章 项目实施',
    level: 1,
    element_count: 35,
    children: []
  }
]

// Mock 元素列表
export const mockElements: DocElement[] = [
  {
    element_id: 'e1',
    doc_title: '项目招标文件.pdf',
    type: 'text',
    content: '本项目旨在建设一个智能化的知识管理系统，实现知识的沉淀、共享和应用。系统需具备知识采集、知识组织、知识检索、知识推送等核心功能。',
    node_id: 'n1-1',
    node_title: '1.1 项目背景',
    page_number: 1,
    seq: 1
  },
  {
    element_id: 'e2',
    doc_title: '项目招标文件.pdf',
    type: 'table',
    content: JSON.stringify({
      headers: ['功能模块', '功能描述', '优先级'],
      rows: [
        ['知识采集', '支持多种格式文档的上传和解析', '高'],
        ['知识组织', '自动构建知识图谱和标签体系', '高'],
        ['知识检索', '智能语义检索和关联推荐', '高']
      ]
    }),
    node_id: 'n1-1',
    node_title: '1.1 项目背景',
    page_number: 2,
    seq: 2
  },
  {
    element_id: 'e3',
    doc_title: '项目招标文件.pdf',
    type: 'heading',
    content: '1.2 项目目标',
    node_id: 'n1-2',
    node_title: '1.2 项目目标',
    page_number: 3,
    seq: 1
  }
]

// Mock 解析任务
export const mockParseTask: ParseTask = {
  task_id: 'task1',
  doc_id: 'doc3',
  status: 'parsing',
  pct: 65
}
