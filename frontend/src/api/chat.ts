// 对话 API
import request from './request'
import type { Conversation, ChatMessage, Scene } from '@/types/chat'

// ========== 会话管理 ==========

export function getConversations(): Promise<Conversation[]> {
  return request.get('/chat/conversations')
}

export function createConversation(title?: string): Promise<Conversation> {
  return request.post('/chat/conversations', { title })
}

export function deleteConversation(id: string): Promise<void> {
  return request.delete('/chat/conversations/' + id)
}

export function getHistory(convId: string): Promise<ChatMessage[]> {
  return request.get('/chat/conversations/' + convId + '/messages')
}

// ========== 对话（SSE） ==========

export function getChatUrl(): string {
  const baseUrl = import.meta.env.VITE_API_BASE || '/api/v2'
  return baseUrl + '/chat'
}

// ========== 引用详情 ==========

export function getElementDetail(elementId: string): Promise<any> {
  return request.get('/elements/' + elementId)
}

export function getElementContext(elementId: string, window = 3): Promise<any[]> {
  return request.get('/elements/' + elementId + '/context', { params: { window } })
}

// ========== 场景 ==========

export function getScenes(): Promise<Scene[]> {
  return request.get('/scenes')
}

// ========== 反馈 ==========

export function sendFeedback(data: { messageId: string; type: 'like' | 'dislike' }): Promise<void> {
  return request.post('/feedback', data)
}

