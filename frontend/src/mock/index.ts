// Mock 入口文件
// 通过覆盖 axios 的 adapter 实现请求级拦截：在发起真实网络请求之前
// 就短路返回 mock 数据。注意——必须改写 adapter，而不是用
// interceptors.response.use：响应成功拦截器只有在真实请求成功返回后才会
// 执行，若没有后端，请求会直接失败走 error 分支，那种 mock 永远不会生效。
import type { AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
// 官方导出的深路径（见 axios package.json 的 exports），用于未命中 mock 时的回落
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore - 该深路径未随包提供类型声明，见 vite-env.d.ts 中的模块声明
import xhrAdapter from 'axios/lib/adapters/xhr.js'
import { mockLoginResponse, mockRefreshResponse, mockUserInfoResponse, mockLogoutResponse } from './auth'
import { handleKnowledgeMock, mockTree, mockElements, mockParseTask } from './knowledge'
import { mockMessages, mockScenes } from './chat'
import { handleWorkflowMock } from './workflow'
import { mockTools, createMockTestResult } from './tool'
import { mockSkills } from './skill'
import { mockMcps, createMockTestResult as createMcpTestResult } from './mcp'
import { mockAgents } from './agent'
import { mockTodos, submitMockTodo } from './todo'
import { mockModels } from './settings'
import type { Tool } from '@/types/tool'
import type { Skill } from '@/types/skill'
import type { Mcp } from '@/types/mcp'
import type { ParseTask } from '@/types/knowledge'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

// Mock 数据存储（供其它模块读写共享状态）
export const mockData: Record<string, unknown> = {}

// 可变的会话列表（支持增删）
let mockConversations = [
  {
    id: 'conv1',
    title: '标书技术方案分析',
    lastTime: '2026-08-03 18:00:00',
    msgCount: 4
  },
  {
    id: 'conv2',
    title: '合同条款解读',
    lastTime: '2026-08-02 14:30:00',
    msgCount: 2
  },
  {
    id: 'conv3',
    title: '项目实施方案建议',
    lastTime: '2026-08-01 09:15:00',
    msgCount: 6
  }
]

// 解析请求体（兼容 axios transformRequest 后的字符串与原始对象）
function parseRequestData(raw: unknown): Record<string, unknown> {
  if (!raw) return {}
  if (typeof raw === 'string') {
    try {
      const parsed: unknown = JSON.parse(raw)
      return typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)
        ? (parsed as Record<string, unknown>)
        : {}
    } catch {
      return {}
    }
  }
  return typeof raw === 'object' && raw !== null && !Array.isArray(raw)
    ? (raw as Record<string, unknown>)
    : {}
}

function requestString(data: Record<string, unknown>, key: string, fallback = ''): string {
  const value = data[key]
  return typeof value === 'string' && value ? value : fallback
}

function requestNumber(data: Record<string, unknown>, key: string, fallback: number): number {
  const value = data[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function requestBoolean(data: Record<string, unknown>, key: string, fallback: boolean): boolean {
  const value = data[key]
  return typeof value === 'boolean' ? value : fallback
}

function requestList<T>(data: Record<string, unknown>, key: string): T[] {
  const value = data[key]
  return Array.isArray(value) ? (value as T[]) : []
}

// 成功响应体的统一封装
function ok(data: unknown) {
  return { code: 0, message: 'success', data }
}

// 根据请求配置匹配 mock 路由，返回完整响应体（{ code, message, data }）；未命中返回 null
function withParams(url: string, params: unknown): string {
  if (!params || typeof params !== 'object' || Array.isArray(params)) return url
  const entries = Object.entries(params as Record<string, unknown>).filter(([, value]) => value !== undefined && value !== null)
  if (!entries.length) return url
  const query = entries.map(([key, value]) => {
    const serialized = typeof value === 'object' ? JSON.stringify(value) : String(value)
    return `${encodeURIComponent(key)}=${encodeURIComponent(serialized)}`
  }).join('&')
  return url.includes('?') ? `${url}&${query}` : `${url}?${query}`
}

function matchMock(config: InternalAxiosRequestConfig): unknown | null {
  const url = config.url || ''
  const method = config.method?.toUpperCase() || 'GET'
  const requestData = parseRequestData(config.data)
  const knowledgeMock = handleKnowledgeMock(withParams(url, config.params), method, requestData)
  if (knowledgeMock !== null) {
    return knowledgeMock
  }

  // ========== 认证相关 ==========
  if (url.includes('/auth/login') && method === 'POST') {
    return mockLoginResponse
  }
  if (url.includes('/auth/refresh') && method === 'POST') {
    return mockRefreshResponse
  }
  if (url.includes('/auth/user-info') && method === 'GET') {
    return mockUserInfoResponse
  }
  if (url.includes('/auth/logout') && method === 'POST') {
    return mockLogoutResponse
  }

  // ========== 结构树与解析任务 ==========
  if (url.includes('/documents/') && url.includes('/tree')) {
    return ok(mockTree)
  } else if (url.includes('/documents/') && url.includes('/elements')) {
    return ok({ list: mockElements, total: mockElements.length })
  } else if (url.includes('/parse-tasks/')) {
    // 模拟解析任务详情
    const taskMatch = url.match(/\/parse-tasks\/([^\/]+)/)
    if (taskMatch) {
      const task: ParseTask = {
        id: taskMatch[1],
        docId: 'doc1',
        status: 'done',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        progress: 100,
        result: mockParseTask
      }
      return ok(task)
    }
  }

  // ========== 对话相关 ==========
  if (url.includes('/chat/conversations')) {
    if (method === 'GET') {
      // GET /chat/conversations - 获取列表
      return ok(mockConversations)
    } else if (method === 'POST') {
      // POST /chat/conversations - 创建会话
      const title = requestString(requestData, 'title', '新对话')
      const agentId = requestString(requestData, 'agentId', '')
        const agentName = requestString(requestData, 'agentName', '')
        const newConv = {
        id: 'conv' + Date.now(),
        title: title,
        lastTime: new Date().toISOString(),
        msgCount: 0,
          agentId,
          agentName
      }
      mockConversations.unshift(newConv)
      return ok(newConv)
    } else if (method === 'DELETE') {
      // DELETE /chat/conversations/:id - 删除会话
      const deleteMatch = url.match(/\/chat\/conversations\/([^\/]+)/)
      if (deleteMatch) {
        const index = mockConversations.findIndex(c => c.id === deleteMatch[1])
        if (index > -1) {
          mockConversations.splice(index, 1)
          return ok({ success: true })
        }
        return { code: 404, message: '会话不存在', data: null }
      }
    }
  } else if (url.includes('/chat/conversations/') && url.includes('/messages')) {
    return ok(mockMessages)
  } else if (url.includes('/scenes')) {
    return ok(mockScenes)
  }

  // ========== 工作流相关 ==========
  if (url.includes('/workflows') || url.includes('/templates') || url.includes('/executions')) {
    const result = handleWorkflowMock(url, method, requestData)
    if (result) {
      return result
    }
  }

  // ========== 工具/技能/MCP 测试 ==========
  if (url.includes('/tools/') && url.includes('/test')) {
    return ok(createMockTestResult())
  }
  if (url.includes('/skills/') && url.includes('/test')) {
    return ok(createMockTestResult())
  }
  if (url.includes('/mcps/') && url.includes('/test')) {
    return ok(createMcpTestResult())
  }

  // ========== 工具相关 ==========
  if (url.includes('/tools')) {
    if (method === 'GET') {
      return ok(mockTools)
    } else if (method === 'POST') {
      const newTool: Tool = {
        id: 'tool' + Date.now(),
        name: requestString(requestData, 'name', '新工具'),
        desc: requestString(requestData, 'desc', ''),
        type: requestString(requestData, 'type', 'api'),
        config: requestData.config as Record<string, unknown> || {},
        enabled: requestBoolean(requestData, 'enabled', true),
        createdAt: new Date().toISOString()
      }
      mockTools.push(newTool)
      return ok(newTool)
    } else if (method === 'PUT') {
      const updateMatch = url.match(/\/tools\/([^\/]+)/)
      if (updateMatch) {
        const index = mockTools.findIndex(t => t.id === updateMatch[1])
        if (index > -1) {
          mockTools[index] = { ...mockTools[index], ...requestData }
          return ok(mockTools[index])
        }
      }
    } else if (method === 'DELETE') {
      const deleteMatch = url.match(/\/tools\/([^\/]+)/)
      if (deleteMatch) {
        const index = mockTools.findIndex(t => t.id === deleteMatch[1])
        if (index > -1) {
          mockTools.splice(index, 1)
          return ok({ success: true })
        }
      }
    }
  }

  // ========== 技能相关 ==========
  if (url.includes('/skills')) {
    if (method === 'GET') {
      return ok(mockSkills)
    } else if (method === 'POST') {
      const newSkill: Skill = {
        id: 'skill' + Date.now(),
        name: requestString(requestData, 'name', '新技能'),
        desc: requestString(requestData, 'desc', ''),
        code: requestString(requestData, 'code', ''),
        enabled: requestBoolean(requestData, 'enabled', true),
        createdAt: new Date().toISOString()
      }
      mockSkills.push(newSkill)
      return ok(newSkill)
    } else if (method === 'PUT') {
      const updateMatch = url.match(/\/skills\/([^\/]+)/)
      if (updateMatch) {
        const index = mockSkills.findIndex(s => s.id === updateMatch[1])
        if (index > -1) {
          mockSkills[index] = { ...mockSkills[index], ...requestData }
          return ok(mockSkills[index])
        }
      }
    } else if (method === 'DELETE') {
      const deleteMatch = url.match(/\/skills\/([^\/]+)/)
      if (deleteMatch) {
        const index = mockSkills.findIndex(s => s.id === deleteMatch[1])
        if (index > -1) {
          mockSkills.splice(index, 1)
          return ok({ success: true })
        }
      }
    }
  }

  // ========== MCP 相关 ==========
  if (url.includes('/mcps')) {
    if (method === 'GET') {
      return ok(mockMcps)
    } else if (method === 'POST') {
      const newMcp: Mcp = {
        id: 'mcp' + Date.now(),
        name: requestString(requestData, 'name', '新 MCP'),
        desc: requestString(requestData, 'desc', ''),
        type: requestString(requestData, 'type', 'sse'),
        url: requestString(requestData, 'url', ''),
        enabled: requestBoolean(requestData, 'enabled', true),
        createdAt: new Date().toISOString()
      }
      mockMcps.push(newMcp)
      return ok(newMcp)
    } else if (method === 'PUT') {
      const updateMatch = url.match(/\/mcps\/([^\/]+)/)
      if (updateMatch) {
        const index = mockMcps.findIndex(m => m.id === updateMatch[1])
        if (index > -1) {
          mockMcps[index] = { ...mockMcps[index], ...requestData }
          return ok(mockMcps[index])
        }
      }
    } else if (method === 'DELETE') {
      const deleteMatch = url.match(/\/mcps\/([^\/]+)/)
      if (deleteMatch) {
        const index = mockMcps.findIndex(m => m.id === deleteMatch[1])
        if (index > -1) {
          mockMcps.splice(index, 1)
          return ok({ success: true })
        }
      }
    }
  }

  // ========== 设置相关 ==========
  if (url.includes('/settings/models')) {
    if (method === 'GET') {
      // 获取所有模型，按 group 过滤
      const groupMatch = url.match(/group=(\w+)/)
      if (groupMatch) {
        const group = groupMatch[1]
        const models = mockModels[group as keyof typeof mockModels] || []
        return ok(models)
      }
      // 返回所有模型
      return ok(mockModels)
    }
  }

  // ========== 智能体相关 ==========
  if (url.includes('/agents')) {
    if (method === 'GET') {
      // GET /agents - 获取列表
      if (url.match(/^\/agents$/) || url.match(/^\/agents\?/)) {
        return ok(mockAgents)
      }
      // GET /agents/:id - 获取详情
      const detailMatch = url.match(/\/agents\/([^\/]+)/)
      if (detailMatch) {
        const agent = mockAgents.find(a => a.id === detailMatch[1])
        if (agent) {
          return ok(agent)
        }
        return { code: 404, message: '智能体不存在', data: null }
      }
    } else if (method === 'POST') {
      // POST /agents - 创建智能体
      const newAgent = {
        id: 'agent' + Date.now(),
        name: requestString(requestData, 'name', '新智能体'),
        desc: requestString(requestData, 'desc', ''),
        model: requestString(requestData, 'model', 'gpt-4o'),
        prompt: requestString(requestData, 'prompt', '你是一个智能助手'),
        temp: requestNumber(requestData, 'temp', 0.7),
        maxtok: requestString(requestData, 'maxtok', '2048'),
        tools: requestList<string>(requestData, 'tools'),
        docs: requestList<string>(requestData, 'docs'),
        wfs: requestList<string>(requestData, 'wfs'),
        mcps: requestList<string>(requestData, 'mcps'),
        skills: requestList<string>(requestData, 'skills'),
        enabled: requestBoolean(requestData, 'enabled', true),
        createdAt: new Date().toISOString(),
        lastActive: new Date().toISOString()
      }
      mockAgents.push(newAgent)
      return ok(newAgent)
    } else if (method === 'PUT') {
      // PUT /agents/:id - 更新智能体
      const updateMatch = url.match(/\/agents\/([^\/]+)/)
      if (updateMatch) {
        const index = mockAgents.findIndex(a => a.id === updateMatch[1])
        if (index > -1) {
          mockAgents[index] = { ...mockAgents[index], ...requestData }
          return ok(mockAgents[index])
        }
        return { code: 404, message: '智能体不存在', data: null }
      }
    } else if (method === 'DELETE') {
      // DELETE /agents/:id - 删除智能体
      const deleteMatch = url.match(/\/agents\/([^\/]+)/)
      if (deleteMatch) {
        const index = mockAgents.findIndex(a => a.id === deleteMatch[1])
        if (index > -1) {
          mockAgents.splice(index, 1)
          return ok({ success: true })
        }
        return { code: 404, message: '智能体不存在', data: null }
      }
    }
  }

  // ========== 待办相关 ==========
  if (url.includes('/todos')) {
    if (method === 'GET') {
      // GET /todos - 获取列表
      return ok(mockTodos)
    } else if (method === 'POST') {
      // POST /todos/:id/submit - 提交待办
      const submitMatch = url.match(/\/todos\/([^\/]+)\/submit/)
      if (submitMatch) {
        const result = submitMockTodo(submitMatch[1], requestData)
        if (result) {
          return ok(result)
        }
        return { code: 404, message: '待办不存在', data: null }
      }
    } else if (method === 'PUT') {
      // PUT /todos/:id - 更新待办
      const updateMatch = url.match(/\/todos\/([^\/]+)/)
      if (updateMatch) {
        const todo = mockTodos.find(t => t.id === updateMatch[1])
        if (todo) {
          Object.assign(todo, requestData)
          return ok(todo)
        }
        return { code: 404, message: '待办不存在', data: null }
      }
    }
  }
  return null
}

// 安装 mock：覆盖 axios adapter，命中 mock 的请求直接返回，不发起网络请求
export function setupMock(service: AxiosInstance) {
  if (!USE_MOCK) return

  service.defaults.adapter = async function mockAdapter(
    config: InternalAxiosRequestConfig
  ): Promise<AxiosResponse> {
    const body = matchMock(config)

    if (body !== null) {
      // 构造一个"成功响应"，交给后续 response 拦截器正常处理（request.ts 里 code===0 的分支）
      return {
        data: body,
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
        request: {}
      } as AxiosResponse
    }

    // 未命中 mock 的请求回落到真实 adapter（默认 xhr）
    if (typeof xhrAdapter === 'function') {
      return xhrAdapter(config)
    }
    throw new Error('[Mock] 未匹配到 mock 路由且无可用真实 adapter：' + (config.url || ''))
  }

  console.log('[Mock] Mock mode enabled (adapter-level)')
}

export default setupMock
