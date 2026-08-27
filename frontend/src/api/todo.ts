// 待办 API
import request from './request'
import type { Todo } from '@/types/todo'

// ========== 待办 CRUD ==========

export function getTodos(status?: 'pending' | 'done'): Promise<Todo[]> {
  return request.get('/todos' + (status ? `?status=${status}` : ''))
}

export function getTodo(id: string): Promise<Todo> {
  return request.get('/todos/' + id)
}

export function submitTodo(id: string, formData: Record<string, unknown>): Promise<Todo> {
  return request.post('/todos/' + id + '/submit', formData)
}

export function rejectTodo(id: string): Promise<Todo> {
  return request.post('/todos/' + id + '/reject')
}