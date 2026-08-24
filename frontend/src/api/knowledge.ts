// 知识库 API
import request from './request'
import type {
  ChunkAsset,
  DocElement,
  Document,
  KnowledgeBase,
  MetadataField,
  MetadataFieldPayload,
  MetadataScope,
  ParseTask,
  RetrievalRunPayload,
  RetrievalSettings,
  RetrievalSettingsPayload,
  RetrievalTestCase,
  RetrievalTestCasePayload,
  RetrievalTestCaseResult,
  RetrievalTestRun,
  RetrievalTestSet,
  RetrievalTestSetPayload,
  TreeNode,
} from '@/types/knowledge'

interface ListResult<T> {
  list: T[]
  total: number
}

interface ImpactResult {
  success: boolean
  affected_count: number
}

interface UpdatedResult {
  updated: number
}

interface QueuedResult {
  queued: boolean
}

interface SuccessResult {
  success: boolean
}

// ========== 知识库 CRUD ==========

export function getKbList(params?: { keyword?: string }): Promise<KnowledgeBase[]> {
  return request.get('/knowledge', { params })
}

export function getKbDetail(id: string): Promise<KnowledgeBase> {
  return request.get('/knowledge/' + id)
}

export function createKb(data: Partial<KnowledgeBase>): Promise<KnowledgeBase> {
  return request.post('/knowledge', data)
}

export function updateKb(id: string, data: Partial<KnowledgeBase>): Promise<KnowledgeBase> {
  return request.put('/knowledge/' + id, data)
}

export function deleteKb(id: string): Promise<SuccessResult> {
  return request.delete('/knowledge/' + id)
}

// ========== 元数据 Schema ==========

export function getMetadataFields(kbId: string, scope?: MetadataScope): Promise<MetadataField[]> {
  return request.get(`/knowledge/${kbId}/metadata-fields`, { params: { scope } })
}

export function createMetadataField(
  kbId: string,
  data: MetadataFieldPayload
): Promise<MetadataField> {
  return request.post(`/knowledge/${kbId}/metadata-fields`, data)
}

export function updateMetadataField(
  kbId: string,
  id: string,
  data: Partial<MetadataField>
): Promise<MetadataField> {
  return request.put(`/knowledge/${kbId}/metadata-fields/${id}`, data)
}

export function deleteMetadataField(
  kbId: string,
  id: string,
  force: boolean
): Promise<ImpactResult> {
  return request.delete(`/knowledge/${kbId}/metadata-fields/${id}`, { params: { force } })
}

// ========== 文档管理 ==========

export function getDocumentList(params: Record<string, unknown>): Promise<ListResult<Document>> {
  return request.get('/documents', { params })
}

export function getDocumentDetail(id: string): Promise<Document> {
  return request.get('/documents/' + id)
}

export function deleteDocument(id: string): Promise<SuccessResult> {
  return request.delete('/documents/' + id)
}

export function updateDocumentMetadata(
  id: string,
  metadata: Record<string, unknown>
): Promise<Document> {
  return request.patch(`/documents/${id}/metadata`, { metadata })
}

export function batchUpdateDocumentMetadata(
  ids: string[],
  metadata: Record<string, unknown>
): Promise<UpdatedResult> {
  return request.post('/documents/batch-metadata', { ids, metadata })
}

export function updateDocumentStatus(ids: string[], enabled: boolean): Promise<UpdatedResult> {
  return request.post('/documents/batch-status', { ids, enabled })
}

// ========== 分段管理 ==========

export function getChunkList(params: Record<string, unknown>): Promise<ListResult<ChunkAsset>> {
  return request.get('/chunks', { params })
}

export function updateChunkMetadata(
  id: string,
  metadata: Record<string, unknown>
): Promise<ChunkAsset> {
  return request.patch(`/chunks/${id}/metadata`, { metadata })
}

export function batchUpdateChunkMetadata(
  ids: string[],
  metadata: Record<string, unknown>
): Promise<UpdatedResult> {
  return request.post('/chunks/batch-metadata', { ids, metadata })
}

export function updateChunkStatus(ids: string[], enabled: boolean): Promise<UpdatedResult> {
  return request.post('/chunks/batch-status', { ids, enabled })
}

export function reembedChunks(
  kbId: string,
  documentIds: string[],
  chunkIds: string[]
): Promise<QueuedResult> {
  return request.post('/chunks/reembed', {
    kb_id: kbId,
    document_ids: documentIds,
    chunk_ids: chunkIds
  })
}

// ========== 检索配置 ==========

export function getRetrievalSettings(kbId: string): Promise<RetrievalSettings> {
  return request.get(`/knowledge/${kbId}/retrieval-settings`)
}

export function saveRetrievalSettings(
  kbId: string,
  payload: RetrievalSettingsPayload
): Promise<RetrievalSettings> {
  return request.put(`/knowledge/${kbId}/retrieval-settings`, payload)
}

// ========== 召回测试 ==========

export function getTestSets(
  kbId: string,
  includeArchived?: boolean
): Promise<ListResult<RetrievalTestSet>> {
  return request.get(`/knowledge/${kbId}/retrieval-test-sets`, {
    params: { include_archived: includeArchived }
  })
}

export function getTestSet(id: string): Promise<RetrievalTestSet> {
  return request.get('/retrieval-test-sets/' + id)
}

export function createTestSet(
  kbId: string,
  payload: RetrievalTestSetPayload
): Promise<RetrievalTestSet> {
  return request.post(`/knowledge/${kbId}/retrieval-test-sets`, payload)
}

export function updateTestSet(
  id: string,
  payload: RetrievalTestSetPayload
): Promise<RetrievalTestSet> {
  return request.put('/retrieval-test-sets/' + id, payload)
}

export function deleteTestSet(id: string): Promise<SuccessResult> {
  return request.delete('/retrieval-test-sets/' + id)
}

export function getTestCases(
  setId: string,
  params?: Record<string, unknown>
): Promise<ListResult<RetrievalTestCase>> {
  return request.get(`/retrieval-test-sets/${setId}/cases`, { params })
}

export function createTestCase(
  setId: string,
  payload: RetrievalTestCasePayload
): Promise<RetrievalTestCase> {
  return request.post(`/retrieval-test-sets/${setId}/cases`, payload)
}

export function updateTestCase(
  caseId: string,
  payload: RetrievalTestCasePayload
): Promise<RetrievalTestCase> {
  return request.put('/retrieval-test-cases/' + caseId, payload)
}

export function deleteTestCase(caseId: string): Promise<SuccessResult> {
  return request.delete('/retrieval-test-cases/' + caseId)
}

export function updateTestCaseStatus(
  ids: string[],
  enabled: boolean
): Promise<UpdatedResult> {
  return request.post('/retrieval-test-cases/batch-status', { ids, enabled })
}

export function getTestRuns(setId: string): Promise<ListResult<RetrievalTestRun>> {
  return request.get(`/retrieval-test-sets/${setId}/runs`)
}

export function startTestRun(
  setId: string,
  payload: RetrievalRunPayload
): Promise<RetrievalTestRun> {
  return request.post(`/retrieval-test-sets/${setId}/runs`, payload)
}

export function getTestRun(runId: string): Promise<RetrievalTestRun> {
  return request.get('/retrieval-test-runs/' + runId)
}

export function cancelTestRun(runId: string): Promise<RetrievalTestRun> {
  return request.post(`/retrieval-test-runs/${runId}/cancel`)
}

export function getTestRunResults(
  runId: string
): Promise<ListResult<RetrievalTestCaseResult>> {
  return request.get(`/retrieval-test-runs/${runId}/cases`)
}

// ========== 上传与解析 ==========

export function uploadDocument(formData: FormData): Promise<{ task_id: string; doc_id: string }> {
  return request.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function getParseTask(taskId: string): Promise<ParseTask> {
  return request.get('/parse-tasks/' + taskId)
}

// ========== 结构树与元素 ==========

export function getDocTree(docId: string): Promise<TreeNode[]> {
  return request.get('/documents/' + docId + '/tree')
}

export function getDocElements(params: {
  docId: string
  nodeId?: string
  type?: string
  page?: number
  pageSize?: number
}): Promise<ListResult<DocElement>> {
  const { docId, ...rest } = params
  return request.get('/documents/' + docId + '/elements', { params: rest })
}
