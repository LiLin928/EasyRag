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
import { mockLoginResponse, mockRefreshResponse, mockUserInfoResponse } from './auth'
import { handleKnowledgeMock, mockTree, mockElements, mockParseTask } from './knowledge'
import { mockConversations, mockMessages, mockScenes } from './chat'
import { handleWorkflowMock } from './workflow'
import { mockTools, createMockTestResult } from './tool'
import { mockSkills } from './skill'
import { mockMcps, createMockTestResult as createMcpTestResult } from './mcp'
import type { Tool } from '@/types/tool'
import type { Skill } from '@/types/skill'
import type { Mcp } from '@/types/mcp'
import type { ParseTask } from '@/types/knowledge'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

// Mock 数据存储（供其它模块读写共享状态）
export const mockData: Record<string, unknown> = {}

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

  // ========== 结构树与解析任务 ==========
  if (url.includes('/documents/') && url.includes('/tree')) {
    return ok(mockTree)
  } else if (url.includes('/documents/') && url.includes('/elements')) {
    return ok({ list: mockElements, total: mockElements.length })
  } else if (url.includes('/parse-tasks/')) {
    // 模拟解析进度递增
    const task: ParseTask = { ...mockParseTask }
    task.pct = Math.min(100, task.pct + Math.random() * 20)
    if (task.pct >= 100) {
      task.status = 'done'
    }
    return ok(task)
  }

  // ========== 对话相关 ==========
  if (url.includes('/chat/conversations') && method === 'GET') {
    return ok(mockConversations)
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

  // ========== 工具相关 ==========
  if (url.includes('/tools') && !url.includes('/test')) {
    if (method === 'GET') {
      // GET /tools - 获取列表
      if (url.match(/^\/tools$/) || url.match(/^\/tools\?/)) {
        return ok(mockTools)
      }
      // GET /tools/:id - 获取详情
      const detailMatch = url.match(/\/tools\/([^\/]+)/)
      if (detailMatch && !url.includes('/test')) {
        const tool = mockTools.find(t => t.id === detailMatch[1])
        if (tool) {
          return ok(tool)
        }
        return { code: 404, message: '工具不存在', data: null }
      }
    } else if (method === 'POST') {
      // POST /tools - 创建工具
      const newTool: Tool = {
        id: 'tool' + Date.now(),
        name: requestString(requestData, 'name'),
        type: requestString(requestData, 'type', 'HTTP') as Tool['type'],
        desc: requestString(requestData, 'desc'),
        sig: requestString(requestData, 'sig'),
        enabled: requestBoolean(requestData, 'enabled', true),
        params: requestList<Tool['params'][number]>(requestData, 'params'),
        auth: (requestData.auth instanceof Object && 'mode' in requestData.auth
          ? requestData.auth
          : { mode: 'none', key: '' }) as Tool['auth'],
        createdAt: new Date().toISOString()
      }
      mockTools.push(newTool)
      return ok(newTool)
    } else if (method === 'PUT') {
      // PUT /tools/:id - 更新工具
      const updateMatch = url.match(/\/tools\/([^\/]+)/)
      if (updateMatch) {
        const index = mockTools.findIndex(t => t.id === updateMatch[1])
        if (index > -1) {
          mockTools[index] = { ...mockTools[index], ...requestData }
          return ok(mockTools[index])
        }
        return { code: 404, message: '工具不存在', data: null }
      }
    } else if (method === 'DELETE') {
      // DELETE /tools/:id - 删除工具
      const deleteMatch = url.match(/\/tools\/([^\/]+)/)
      if (deleteMatch) {
        const index = mockTools.findIndex(t => t.id === deleteMatch[1])
        if (index > -1) {
          mockTools.splice(index, 1)
          return ok({ success: true })
        }
        return { code: 404, message: '工具不存在', data: null }
      }
    }
  } else if (url.includes('/tools/') && url.includes('/test') && method === 'POST') {
    // POST /tools/:id/test - 测试工具
    const testMatch = url.match(/\/tools\/([^\/]+)\/test/)
    if (testMatch) {
      const toolId = testMatch[1]
      const result = createMockTestResult(toolId, requestData)
      return ok(result)
    }
  }

  // ========== 技能相关 ==========
  if (url.includes('/skills') && !url.includes('/duplicate')) {
    if (method === 'GET') {
      // GET /skills - 获取列表
      if (url.match(/^\/skills$/) || url.match(/^\/skills\?/)) {
        return ok(mockSkills)
      }
      // GET /skills/:id - 获取详情
      const detailMatch = url.match(/\/skills\/([^\/]+)/)
      if (detailMatch && !url.includes('/duplicate')) {
        const skill = mockSkills.find(s => s.id === detailMatch[1])
        if (skill) {
          return ok(skill)
        }
        return { code: 404, message: '技能不存在', data: null }
      }
    } else if (method === 'POST') {
      // POST /skills - 创建技能
      const newSkill: Skill = {
        id: 'skill' + Date.now(),
        ico: requestString(requestData, 'ico', '🔧'),
        name: requestString(requestData, 'name'),
        scope: 'custom',
        ver: '1.0.0',
        desc: requestString(requestData, 'desc'),
        trigger: requestString(requestData, 'trigger'),
        prompt: requestString(requestData, 'prompt'),
        tools: requestList<Skill['tools'][number]>(requestData, 'tools'),
        docs: requestList<Skill['docs'][number]>(requestData, 'docs'),
        wfs: requestList<Skill['wfs'][number]>(requestData, 'wfs'),
        examples: requestList<Skill['examples'][number]>(requestData, 'examples'),
        scripts: requestList<Skill['scripts'][number]>(requestData, 'scripts'),
        budget: requestNumber(requestData, 'budget', 100),
        used: 0
      }
      mockSkills.push(newSkill)
      return ok(newSkill)
    } else if (method === 'PUT') {
      // PUT /skills/:id - 更新技能
      const updateMatch = url.match(/\/skills\/([^\/]+)/)
      if (updateMatch) {
        const index = mockSkills.findIndex(s => s.id === updateMatch[1])
        if (index > -1) {
          mockSkills[index] = { ...mockSkills[index], ...requestData }
          return ok(mockSkills[index])
        }
        return { code: 404, message: '技能不存在', data: null }
      }
    } else if (method === 'DELETE') {
      // DELETE /skills/:id - 删除技能
      const deleteMatch = url.match(/\/skills\/([^\/]+)/)
      if (deleteMatch) {
        const index = mockSkills.findIndex(s => s.id === deleteMatch[1])
        if (index > -1) {
          // 内置技能不可删除
          if (mockSkills[index].scope === 'builtin') {
            return { code: 403, message: '内置技能不可删除', data: null }
          }
          mockSkills.splice(index, 1)
          return ok({ success: true })
        }
        return { code: 404, message: '技能不存在', data: null }
      }
    }
  } else if (url.includes('/skills/') && url.includes('/duplicate') && method === 'POST') {
    // POST /skills/:id/duplicate - 复制技能
    const duplicateMatch = url.match(/\/skills\/([^\/]+)\/duplicate/)
    if (duplicateMatch) {
      const originalSkill = mockSkills.find(s => s.id === duplicateMatch[1])
      if (originalSkill) {
        const newSkill: Skill = {
          ...originalSkill,
          id: 'skill' + Date.now(),
          name: originalSkill.name + ' (副本)',
          scope: 'custom',
          ver: '1.0.0',
          used: 0
        }
        mockSkills.unshift(newSkill)
        return ok(newSkill)
      }
      return { code: 404, message: '技能不存在', data: null }
    }
  }

  // ========== MCP 相关 ==========
  if (url.includes('/mcps') && !url.includes('/test')) {
    if (method === 'GET') {
      // GET /mcps - 获取列表
      if (url.match(/^\/mcps$/) || url.match(/^\/mcps\?/)) {
        return ok(mockMcps)
      }
      // GET /mcps/:id - 获取详情
      const detailMatch = url.match(/\/mcps\/([^\/]+)/)
      if (detailMatch && !url.includes('/test')) {
        const mcp = mockMcps.find(m => m.id === detailMatch[1])
        if (mcp) {
          return ok(mcp)
        }
        return { code: 404, message: 'MCP 服务不存在', data: null }
      }
    } else if (method === 'POST') {
      // POST /mcps - 创建 MCP 服务
      const newMcp: Mcp = {
        id: 'mcp' + Date.now(),
        name: requestString(requestData, 'name'),
        tp: requestString(requestData, 'tp', 'stdio') as Mcp['tp'],
        cmd: requestString(requestData, 'cmd'),
        status: 'off',
        toolCount: 0,
        env: requestList<Mcp['env'][number]>(requestData, 'env'),
        timeout: requestNumber(requestData, 'timeout', 30),
        createdAt: new Date().toISOString()
      }
      mockMcps.push(newMcp)
      return ok(newMcp)
    } else if (method === 'PUT') {
      // PUT /mcps/:id - 更新 MCP 服务
      const updateMatch = url.match(/\/mcps\/([^\/]+)/)
      if (updateMatch) {
        const index = mockMcps.findIndex(m => m.id === updateMatch[1])
        if (index > -1) {
          mockMcps[index] = { ...mockMcps[index], ...requestData }
          return ok(mockMcps[index])
        }
        return { code: 404, message: 'MCP 服务不存在', data: null }
      }
    } else if (method === 'DELETE') {
      // DELETE /mcps/:id - 删除 MCP 服务
      const deleteMatch = url.match(/\/mcps\/([^\/]+)/)
      if (deleteMatch) {
        const index = mockMcps.findIndex(m => m.id === deleteMatch[1])
        if (index > -1) {
          mockMcps.splice(index, 1)
          return ok({ success: true })
        }
        return { code: 404, message: 'MCP 服务不存在', data: null }
      }
    }
  } else if (url.includes('/mcps/') && url.includes('/test') && method === 'POST') {
    // POST /mcps/:id/test - 测试 MCP 服务
    const testMatch = url.match(/\/mcps\/([^\/]+)\/test/)
    if (testMatch) {
      const mcpId = testMatch[1]
      const result = createMcpTestResult(mcpId)
      return ok(result)
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
