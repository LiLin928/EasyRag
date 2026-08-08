// 知识库 API
import request from './request'
import type { KnowledgeBase, Document, TreeNode, DocElement, ParseTask } from '@/types/knowledge'

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
