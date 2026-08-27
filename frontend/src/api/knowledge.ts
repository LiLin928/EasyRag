// 知识库 API
import request from './request'
import type {
  KnowledgeBase, Document, TreeNode, DocElement, ParseTask,
  RetrievalSettings, MetadataField, Segment, HitTestResult, HitTestRecord,
  RetrievalTestSet, RetrievalTestCase, RetrievalTestRun
} from '@/types/knowledge'

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

export function deleteKb(id: string): Promise<void> {
  return request.delete('/knowledge/' + id)
}

// ========== 文档管理 ==========

export function getDocumentList(params: { kb_id: string; page?: number; pageSize?: number }): Promise<{
  list: Document[]
  total: number
}> {
  return request.get('/documents', { params })
}

export function getDocumentDetail(id: string): Promise<Document> {
  return request.get('/documents/' + id)
}

export function deleteDocument(id: string): Promise<void> {
  return request.delete('/documents/' + id)
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
}): Promise<{
  list: DocElement[]
  total: number
}> {
  const { docId, ...rest } = params
  return request.get('/documents/' + docId + '/elements', { params: rest })
}

// ========== 检索设置 ==========

export function getRetrievalSettings(kbId: string): Promise<RetrievalSettings> {
  return request.get('/knowledge/' + kbId + '/retrieval-settings')
}

export function updateRetrievalSettings(kbId: string, data: Partial<RetrievalSettings>): Promise<RetrievalSettings> {
  return request.put('/knowledge/' + kbId + '/retrieval-settings', data)
}

// ========== 元数据字段管理 ==========

export function getMetadataFields(kbId: string): Promise<MetadataField[]> {
  return request.get('/knowledge/' + kbId + '/metadata-fields')
}

export function createMetadataField(kbId: string, data: Partial<MetadataField>): Promise<MetadataField> {
  return request.post('/knowledge/' + kbId + '/metadata-fields', data)
}

export function updateMetadataField(fieldId: string, data: Partial<MetadataField>): Promise<MetadataField> {
  return request.put('/knowledge/metadata-fields/' + fieldId, data)
}

export function deleteMetadataField(fieldId: string): Promise<void> {
  return request.delete('/knowledge/metadata-fields/' + fieldId)
}

// ========== 分段管理 ==========

export function getSegments(kbId: string, params?: { docId?: string; page?: number; pageSize?: number }): Promise<{
  list: Segment[]
  total: number
}> {
  return request.get('/chunks', { params: { kb_id: kbId, ...params } })
}

export function updateSegmentMetadata(segmentId: string, data: Record<string, string>): Promise<Segment> {
  return request.put('/chunks/' + segmentId + '/metadata', data)
}

export function updateSegmentStatus(segmentId: string, enabled: boolean): Promise<Segment> {
  return request.put('/chunks/' + segmentId + '/status', { enabled })
}

// ========== 召回测试（即时） ==========

export function hitTest(kbId: string, query: string): Promise<HitTestResult> {
  return request.post('/knowledge/' + kbId + '/hit-test', { query })
}

export function getHitTestRecords(kbId: string): Promise<HitTestRecord[]> {
  return request.get('/knowledge/' + kbId + '/hit-test-records')
}

// ========== 召回测试（批量） ==========

export function getTestSets(kbId: string): Promise<RetrievalTestSet[]> {
  return request.get('/knowledge/' + kbId + '/retrieval-test-sets')
}

export function createTestSet(kbId: string, data: Partial<RetrievalTestSet>): Promise<RetrievalTestSet> {
  return request.post('/knowledge/' + kbId + '/retrieval-test-sets', data)
}

export function getTestCases(testSetId: string): Promise<RetrievalTestCase[]> {
  return request.get('/retrieval-test-sets/' + testSetId + '/cases')
}

export function createTestCase(testSetId: string, data: Partial<RetrievalTestCase>): Promise<RetrievalTestCase> {
  return request.post('/retrieval-test-sets/' + testSetId + '/cases', data)
}

export function updateTestCase(caseId: string, data: Partial<RetrievalTestCase>): Promise<RetrievalTestCase> {
  return request.put('/retrieval-test-cases/' + caseId, data)
}

export function deleteTestCase(caseId: string): Promise<void> {
  return request.delete('/retrieval-test-cases/' + caseId)
}

export function createTestRun(testSetId: string, data: Record<string, unknown>): Promise<RetrievalTestRun> {
  return request.post('/retrieval-test-sets/' + testSetId + '/runs', data)
}

export function getTestRun(runId: string): Promise<RetrievalTestRun> {
  return request.get('/retrieval-test-runs/' + runId)
}
