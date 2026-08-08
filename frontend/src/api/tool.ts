// 工具 API
import request from './request'
import type { Tool, ToolTestArgs, ToolTestResult } from '@/types/tool'

// ========== 工具 CRUD ==========

export function getTools(): Promise<Tool[]> {
  return request.get('/tools')
}

export function getTool(id: string): Promise<Tool> {
  return request.get('/tools/' + id)
}

export function createTool(data: Partial<Tool>): Promise<Tool> {
  return request.post('/tools', data)
}

export function updateTool(id: string, data: Partial<Tool>): Promise<Tool> {
  return request.put('/tools/' + id, data)
}

export function deleteTool(id: string): Promise<void> {
  return request.delete('/tools/' + id)
}

// ========== 工具测试 ==========

export function testTool(id: string, args: ToolTestArgs): Promise<ToolTestResult> {
  return request.post('/tools/' + id + '/test', args)
}
