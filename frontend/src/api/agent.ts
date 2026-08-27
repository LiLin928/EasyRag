// 智能体 API
import request from './request'
import type { Agent } from '@/types/agent'

// ========== 智能体 CRUD ==========

export function getAgents(): Promise<Agent[]> {
  return request.get('/agents')
}

export function getAgent(id: string): Promise<Agent> {
  return request.get('/agents/' + id)
}

export function createAgent(data: Partial<Agent>): Promise<Agent> {
  return request.post('/agents', data)
}

export function updateAgent(id: string, data: Partial<Agent>): Promise<Agent> {
  return request.put('/agents/' + id, data)
}

export function deleteAgent(id: string): Promise<void> {
  return request.delete('/agents/' + id)
}
