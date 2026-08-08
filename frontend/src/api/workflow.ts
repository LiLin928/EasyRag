// 工作流 API
import request from './request'
import type { Workflow, Template, Execution } from '@/types/workflow'

// ========== 工作流列表 ==========

export function getWorkflows(): Promise<Workflow[]> {
  return request.get('/workflows')
}

export function createWorkflow(data: { name: string; description?: string }): Promise<Workflow> {
  return request.post('/workflows', data)
}

export function duplicateWorkflow(id: string): Promise<Workflow> {
  return request.post('/workflows/' + id + '/duplicate')
}

export function deleteWorkflow(id: string): Promise<void> {
  return request.delete('/workflows/' + id)
}

// ========== 工作流详情/更新 ==========

export function getWorkflow(id: string): Promise<Workflow> {
  return request.get('/workflows/' + id)
}

export function updateWorkflow(id: string, data: Partial<Workflow>): Promise<Workflow> {
  return request.put('/workflows/' + id, data)
}

export function publishWorkflow(id: string): Promise<Workflow> {
  return request.post('/workflows/' + id + '/publish')
}

// ========== 模板 ==========

export function getTemplates(): Promise<Template[]> {
  return request.get('/templates')
}

export function createFromTemplate(templateId: string, name?: string): Promise<Workflow> {
  return request.post('/templates/' + templateId + '/instantiate', { name })
}

// ========== 执行 ==========

export function getExecutions(params?: { workflowId?: string; limit?: number }): Promise<Execution[]> {
  return request.get('/executions', { params })
}

export function executeWorkflow(id: string, debug = false): Promise<{ executionId: string }> {
  return request.post('/workflows/' + id + '/execute', { debug })
}

export function getExecutionStreamUrl(executionId: string): string {
  const baseUrl = import.meta.env.VITE_API_BASE || '/api/v2'
  return baseUrl + '/executions/' + executionId + '/stream'
}

export function cancelExecution(executionId: string): Promise<void> {
  return request.post('/executions/' + executionId + '/cancel')
}

export function resumeExecution(executionId: string): Promise<void> {
  return request.post('/executions/' + executionId + '/resume')
}

export function debugContinue(executionId: string): Promise<void> {
  return request.post('/executions/' + executionId + '/debug/continue')
}

export function testNode(executionId: string, nodeId: string): Promise<any> {
  return request.post('/executions/' + executionId + '/debug/test-node', { nodeId })
}

export function getNodeExecDetail(executionId: string, nodeId: string): Promise<any> {
  return request.get('/executions/' + executionId + '/nodes/' + nodeId)
}
