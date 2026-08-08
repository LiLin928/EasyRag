// 技能 API
import request from './request'
import type { Skill } from '@/types/skill'

// ========== 技能 CRUD ==========

export function getSkills(): Promise<Skill[]> {
  return request.get('/skills')
}

export function getSkill(id: string): Promise<Skill> {
  return request.get('/skills/' + id)
}

export function createSkill(data: Partial<Skill>): Promise<Skill> {
  return request.post('/skills', data)
}

export function updateSkill(id: string, data: Partial<Skill>): Promise<Skill> {
  return request.put('/skills/' + id, data)
}

export function deleteSkill(id: string): Promise<void> {
  return request.delete('/skills/' + id)
}

export function duplicateSkill(id: string): Promise<Skill> {
  return request.post('/skills/' + id + '/duplicate')
}
