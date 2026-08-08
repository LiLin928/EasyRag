// MCP API
import request from './request'
import type { Mcp, McpTestResult } from '@/types/mcp'

// ========== MCP CRUD ==========

export function getMcps(): Promise<Mcp[]> {
  return request.get('/mcps')
}

export function getMcp(id: string): Promise<Mcp> {
  return request.get('/mcps/' + id)
}

export function createMcp(data: Partial<Mcp>): Promise<Mcp> {
  return request.post('/mcps', data)
}

export function updateMcp(id: string, data: Partial<Mcp>): Promise<Mcp> {
  return request.put('/mcps/' + id, data)
}

export function deleteMcp(id: string): Promise<void> {
  return request.delete('/mcps/' + id)
}

// ========== MCP 测试 ==========

export function testMcp(id: string): Promise<McpTestResult> {
  return request.post('/mcps/' + id + '/test')
}
