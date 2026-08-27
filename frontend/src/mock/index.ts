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
import {
  mockKnowledgeBases, mockDocuments, mockTree, mockElements, mockParseTask,
  mockRetrievalSettings, mockMetadataFields, mockSegments,
  mockHitTestRecords, createMockHitTestResult,
  mockTestSets, mockTestCases, mockTestRuns, createMockTestRun
} from './knowledge'
import { mockConversations, mockMessages, mockScenes as mockChatScenes } from './chat'
import { handleWorkflowMock } from './workflow'
import { mockTools, createMockTestResult } from './tool'
import { mockSkills } from './skill'
import { mockMcps, createMockTestResult as createMcpTestResult } from './mcp'
import { mockAgents } from './agent'
import { mockTodos, submitMockTodo, rejectMockTodo } from './todo'
import { mockModels, getMockModelsByGroup, mockScenes } from './settings'
import type { Tool } from '@/types/tool'
import type { Skill } from '@/types/skill'
import type { Mcp } from '@/types/mcp'
import type { Agent } from '@/types/agent'
import type { ModelGroup, Scene } from '@/types/settings'
import type { Conversation } from '@/types/chat'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

// Mock 数据存储（供其它模块读写共享状态）
export const mockData: Record<string, any> = {}

// 解析请求体（兼容 axios transformRequest 后的字符串与原始对象）
function parseRequestData(raw: unknown): Record<string, any> {
  if (!raw) return {}
  if (typeof raw === 'string') {
    try {
      return JSON.parse(raw)
    } catch {
      return {}
    }
  }
  return raw as Record<string, any>
}

// 成功响应体的统一封装
function ok(data: unknown) {
  return { code: 0, message: 'success', data }
}

// 根据请求配置匹配 mock 路由，返回完整响应体（{ code, message, data }）；未命中返回 null
function matchMock(config: InternalAxiosRequestConfig): unknown | null {
  const url = config.url || ''
  const method = config.method?.toUpperCase() || 'GET'
  const requestData = parseRequestData(config.data)

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

  // ========== 知识库相关 ==========
  // --- 检索设置 ---
  if (url.includes('/retrieval-settings') && method === 'GET') {
    const kbId = url.match(/\/knowledge\/([^/]+)\/retrieval-settings/)?.[1] || 'kb1'
    return ok(mockRetrievalSettings[kbId] || mockRetrievalSettings['kb1'])
  }
  if (url.includes('/retrieval-settings') && method === 'PUT') {
    const kbId = url.match(/\/knowledge\/([^/]+)\/retrieval-settings/)?.[1] || 'kb1'
    const existing = mockRetrievalSettings[kbId] || mockRetrievalSettings['kb1']
    const updated = { ...existing, ...requestData }
    mockRetrievalSettings[kbId] = updated
    return ok(updated)
  }

  // --- 元数据字段 ---
  if (url.includes('/metadata-fields')) {
    if (url.includes('/metadata-fields/') && (method === 'PUT' || method === 'DELETE')) {
      const fieldId = url.match(/\/metadata-fields\/([^/?]+)/)?.[1]
      if (fieldId) {
        if (method === 'DELETE') {
          for (const kbId of Object.keys(mockMetadataFields)) {
            const idx = mockMetadataFields[kbId].findIndex(f => f.id === fieldId)
            if (idx > -1) {
              mockMetadataFields[kbId].splice(idx, 1)
              break
            }
          }
          return ok({ success: true })
        }
        if (method === 'PUT') {
          for (const kbId of Object.keys(mockMetadataFields)) {
            const idx = mockMetadataFields[kbId].findIndex(f => f.id === fieldId)
            if (idx > -1) {
              mockMetadataFields[kbId][idx] = { ...mockMetadataFields[kbId][idx], ...requestData }
              return ok(mockMetadataFields[kbId][idx])
            }
          }
        }
      }
    }
    if (method === 'GET') {
      const kbId = url.match(/\/knowledge\/([^/]+)\/metadata-fields/)?.[1] || 'kb1'
      return ok(mockMetadataFields[kbId] || mockMetadataFields['kb1'])
    }
    if (method === 'POST') {
      const kbId = url.match(/\/knowledge\/([^/]+)\/metadata-fields/)?.[1] || 'kb1'
      const newField = {
        id: 'cf' + Date.now(),
        kbId,
        key: requestData.key || '',
        name: requestData.name || '',
        scope: requestData.scope || 'document',
        dataType: requestData.dataType || 'string',
        options: requestData.options || [],
        required: requestData.required || false,
        filterable: requestData.filterable !== false,
        retrievalFilterable: requestData.retrievalFilterable || false,
        visible: requestData.visible !== false,
        builtIn: false,
        sortOrder: (mockMetadataFields[kbId] || []).length + 1
      }
      if (!mockMetadataFields[kbId]) mockMetadataFields[kbId] = []
      mockMetadataFields[kbId].push(newField)
      return ok(newField)
    }
  }

  // --- 分段管理 ---
  if (url.match(/^\/chunks/) && method === 'GET') {
    const kbId = url.match(/kb_id=([^&]+)/)?.[1] || 'kb1'
    const list = mockSegments[kbId] || []
    return ok({ list, total: list.length })
  }
  if (url.match(/\/chunks\/([^/]+)\/metadata/) && method === 'PUT') {
    const segId = url.match(/\/chunks\/([^/]+)\/metadata/)?.[1]
    if (segId) {
      for (const kbId of Object.keys(mockSegments)) {
        const seg = mockSegments[kbId].find(s => s.id === segId)
        if (seg) {
          seg.metadata = { ...seg.metadata, ...requestData }
          return ok(seg)
        }
      }
    }
  }
  if (url.match(/\/chunks\/([^/]+)\/status/) && method === 'PUT') {
    const segId = url.match(/\/chunks\/([^/]+)\/status/)?.[1]
    if (segId) {
      for (const kbId of Object.keys(mockSegments)) {
        const seg = mockSegments[kbId].find(s => s.id === segId)
        if (seg) {
          seg.enabled = requestData.enabled
          return ok(seg)
        }
      }
    }
  }

  // --- 召回测试（即时） ---
  if (url.includes('/hit-test') && !url.includes('/records') && method === 'POST') {
    const kbId = url.match(/\/knowledge\/([^/]+)\/hit-test/)?.[1] || 'kb1'
    const result = createMockHitTestResult(requestData.query || '')
    mockHitTestRecords.unshift({
      id: 'hit' + Date.now(),
      kbId,
      query: requestData.query || '',
      source: 'immediate',
      retrievalMode: 'hybrid',
      createdAt: new Date().toISOString().replace('T', ' ').substring(0, 19),
      result
    })
    return ok(result)
  }
  if (url.includes('/hit-test-records') && method === 'GET') {
    const kbId = url.match(/\/knowledge\/([^/]+)\/hit-test-records/)?.[1] || 'kb1'
    return ok(mockHitTestRecords.filter(r => r.kbId === kbId))
  }

  // --- 召回测试（批量） ---
  if (url.includes('/retrieval-test-sets')) {
    if (url.match(/\/retrieval-test-sets\/([^/]+)\/cases/)) {
      const setId = url.match(/\/retrieval-test-sets\/([^/]+)\/cases/)?.[1]
      if (method === 'GET') {
        return ok(mockTestCases.filter(tc => tc.testSetId === setId))
      }
      if (method === 'POST') {
        const newCase = {
          id: 'tc' + Date.now(),
          testSetId: setId || '',
          query: requestData.query || '',
          expectedDocIds: requestData.expectedDocIds || [],
          expectedChunkIds: requestData.expectedChunkIds || [],
          tags: requestData.tags || [],
          enabled: requestData.enabled !== false
        }
        mockTestCases.push(newCase as any)
        return ok(newCase)
      }
    }
    if (url.match(/\/retrieval-test-sets\/([^/]+)\/runs/) && method === 'POST') {
      const setId = url.match(/\/retrieval-test-sets\/([^/]+)\/runs/)?.[1]
      const kbId = requestData.kbId || 'kb1'
      const run = createMockTestRun(setId || '', kbId)
      mockTestRuns.push(run)
      return ok(run)
    }
    if (url.match(/^\/retrieval-test-sets\/([^/]+)$/) || url.match(/\/retrieval-test-sets\/([^/?]+)/)) {
      const setId = url.match(/\/retrieval-test-sets\/([^/?]+)/)?.[1]
      if (method === 'GET') {
        const ts = mockTestSets.find(t => t.id === setId)
        return ok(ts || null)
      }
    }
    if (method === 'GET') {
      const kbId = url.match(/\/knowledge\/([^/]+)\/retrieval-test-sets/)?.[1] || 'kb1'
      return ok(mockTestSets.filter(ts => ts.kbId === kbId))
    }
    if (method === 'POST') {
      const kbId = url.match(/\/knowledge\/([^/]+)\/retrieval-test-sets/)?.[1] || 'kb1'
      const newTs = {
        id: 'ts' + Date.now(),
        kbId,
        name: requestData.name || '',
        description: requestData.description || '',
        caseCount: 0,
        status: 'draft' as const
      }
      mockTestSets.unshift(newTs as any)
      return ok(newTs)
    }
  }
  if (url.includes('/retrieval-test-cases/') && (method === 'PUT' || method === 'DELETE')) {
    const caseId = url.match(/\/retrieval-test-cases\/([^/?]+)/)?.[1]
    if (caseId) {
      if (method === 'DELETE') {
        const idx = mockTestCases.findIndex(tc => tc.id === caseId)
        if (idx > -1) {
          mockTestCases.splice(idx, 1)
          return ok({ success: true })
        }
      }
      if (method === 'PUT') {
        const idx = mockTestCases.findIndex(tc => tc.id === caseId)
        if (idx > -1) {
          mockTestCases[idx] = { ...mockTestCases[idx], ...requestData }
          return ok(mockTestCases[idx])
        }
      }
    }
  }
  if (url.includes('/retrieval-test-runs/') && method === 'GET') {
    const runId = url.match(/\/retrieval-test-runs\/([^/?]+)/)?.[1]
    const run = mockTestRuns.find(r => r.id === runId)
    return ok(run || null)
  }

  // --- 知识库 CRUD ---
  if (url.match(/^\/knowledge(?:\?|$)/) && method === 'GET') {
    return ok(mockKnowledgeBases)
  }
  if (url.match(/\/knowledge\/([^/?]+)$/) && method === 'GET') {
    const kbId = url.match(/\/knowledge\/([^/?]+)/)?.[1]
    const kb = mockKnowledgeBases.find(k => k.id === kbId)
    return ok(kb || null)
  }
  if (url.match(/^\/knowledge(?:\?|$)/) && method === 'POST') {
    const newKb = {
      id: 'kb' + Date.now(),
      name: requestData.name || '',
      desc: requestData.desc || '',
      scene: requestData.scene || 'general',
      docCount: 0,
      totalSize: '0 MB',
      createdAt: new Date().toISOString().replace('T', ' ').substring(0, 19),
      cover: '#409eff',
      chunkMethod: 'general' as const,
      segmentCount: 0
    }
    mockKnowledgeBases.push(newKb)
    return ok(newKb)
  }
  if (url.match(/\/knowledge\/([^/?]+)$/) && method === 'PUT') {
    const kbId = url.match(/\/knowledge\/([^/?]+)/)?.[1]
    const idx = mockKnowledgeBases.findIndex(k => k.id === kbId)
    if (idx > -1) {
      mockKnowledgeBases[idx] = { ...mockKnowledgeBases[idx], ...requestData }
      return ok(mockKnowledgeBases[idx])
    }
    return { code: 404, message: '知识库不存在', data: null }
  }
  if (url.match(/\/knowledge\/([^/?]+)$/) && method === 'DELETE') {
    const kbId = url.match(/\/knowledge\/([^/?]+)/)?.[1]
    const idx = mockKnowledgeBases.findIndex(k => k.id === kbId)
    if (idx > -1) {
      mockKnowledgeBases.splice(idx, 1)
      return ok({ success: true })
    }
    return { code: 404, message: '知识库不存在', data: null }
  }

  // --- 文档管理 ---
  if (url.includes('/documents') && !url.includes('/tree') && !url.includes('/elements') && !url.includes('/chat') && method === 'GET') {
    const kbId = url.match(/kb_id=([^&]+)/)?.[1] || 'kb1'
    const docs = mockDocuments.filter(d => d.kbId === kbId)
    return ok({ list: docs, total: docs.length })
  }
  if (url.includes('/documents/') && url.includes('/tree')) {
    return ok(mockTree)
  }
  if (url.includes('/documents/') && url.includes('/elements')) {
    return ok({ list: mockElements, total: mockElements.length })
  }
  if (url.includes('/parse-tasks/')) {
    const task = { ...mockParseTask }
    task.pct = Math.min(100, task.pct + Math.random() * 20)
    if (task.pct >= 100) {
      task.status = 'done'
    }
    return ok(task)
  }

  // ========== 对话相关 ==========
  if (url.includes('/chat/conversations')) {
    // POST /chat/conversations - 新建会话
    if (method === 'POST') {
      const now = new Date()
      const pad = (n: number) => String(n).padStart(2, '0')
      const newConv: Conversation = {
        id: 'conv' + Date.now(),
        title: requestData.title || '新对话',
        lastTime: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`,
        msgCount: 0
      }
      mockConversations.unshift(newConv)
      return ok(newConv)
    }
    // DELETE /chat/conversations/:id - 删除会话
    if (method === 'DELETE') {
      const delMatch = url.match(/\/chat\/conversations\/([^/?]+)/)
      if (delMatch) {
        const idx = mockConversations.findIndex(c => c.id === delMatch[1])
        if (idx > -1) mockConversations.splice(idx, 1)
        return ok({ success: true })
      }
    }
    // GET /chat/conversations/:id/messages - 历史消息
    if (url.includes('/messages') && method === 'GET') {
      return ok(mockMessages)
    }
    // GET /chat/conversations - 会话列表
    if (method === 'GET') {
      return ok(mockConversations)
    }
  } else if (url === '/scenes' || url.startsWith('/scenes?')) {
    return ok(mockChatScenes)
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
        name: requestData.name || '',
        type: requestData.type || 'HTTP',
        desc: requestData.desc || '',
        sig: requestData.sig || '',
        enabled: requestData.enabled !== false,
        params: requestData.params || [],
        auth: requestData.auth || { mode: 'none', key: '' },
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
        ico: requestData.ico || '🔧',
        name: requestData.name || '',
        scope: 'custom',
        ver: '1.0.0',
        desc: requestData.desc || '',
        trigger: requestData.trigger || '',
        prompt: requestData.prompt || '',
        tools: requestData.tools || [],
        docs: requestData.docs || [],
        wfs: requestData.wfs || [],
        examples: requestData.examples || [],
        scripts: requestData.scripts || [],
        budget: requestData.budget,
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
        name: requestData.name || '',
        tp: requestData.tp || 'stdio',
        cmd: requestData.cmd || '',
        status: 'off',
        toolCount: 0,
        env: requestData.env || [],
        timeout: requestData.timeout || 30,
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

  // ========== 待办相关 ==========
  if (url.includes('/todos') && !url.includes('/submit')) {
    if (method === 'GET') {
      // GET /todos - 获取列表
      const statusMatch = url.match(/[\?&]status=([^&]+)/)
      const status = statusMatch ? statusMatch[1] as 'pending' | 'done' : undefined

      if (url.match(/^\/todos$/) || url.match(/^\/todos\?/)) {
        let filteredTodos = mockTodos
        if (status === 'pending') {
          filteredTodos = mockTodos.filter(t => t.status === 'pending')
        } else if (status === 'done') {
          filteredTodos = mockTodos.filter(t => t.status === 'done' || t.status === 'rejected')
        }
        return ok(filteredTodos)
      }
      // GET /todos/:id - 获取详情
      const detailMatch = url.match(/\/todos\/([^\/]+)/)
      if (detailMatch && !url.includes('/submit')) {
        const todo = mockTodos.find(t => t.id === detailMatch[1])
        if (todo) {
          return ok(todo)
        }
        return { code: 404, message: '待办不存在', data: null }
      }
    }
  } else if (url.includes('/todos/') && url.includes('/submit') && method === 'POST') {
    // POST /todos/:id/submit - 提交代办
    const submitMatch = url.match(/\/todos\/([^\/]+)\/submit/)
    if (submitMatch) {
      const todoId = submitMatch[1]
      const todo = submitMockTodo(todoId, requestData)
      if (todo) {
        return ok(todo)
      }
      return { code: 404, message: '待办不存在', data: null }
    }
  } else if (url.includes('/todos/') && url.includes('/reject') && method === 'POST') {
    // POST /todos/:id/reject - 驳回待办
    const rejectMatch = url.match(/\/todos\/([^\/]+)\/reject/)
    if (rejectMatch) {
      const todoId = rejectMatch[1]
      const todo = rejectMockTodo(todoId)
      if (todo) {
        return ok(todo)
      }
      return { code: 404, message: '待办不存在', data: null }
    }
  }

  // ========== 智能体相关 ==========
  if (url.includes('/agents') && !url.includes('/chat')) {
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
      const newAgent: Agent = {
        id: 'agent' + Date.now(),
        name: requestData.name || '',
        desc: requestData.desc || '',
        model: requestData.model || 'gpt-4o',
        prompt: requestData.prompt || '',
        temp: requestData.temp ?? 0.7,
        maxtok: requestData.maxtok || '2048',
        tools: requestData.tools || [],
        docs: requestData.docs || [],
        wfs: requestData.wfs || [],
        mcps: requestData.mcps || [],
        skills: requestData.skills || [],
        enabled: requestData.enabled !== false,
        lastActive: new Date().toISOString(),
        createdAt: new Date().toISOString()
      }
      mockAgents.unshift(newAgent)
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

  // ========== 系统设置相关 ==========
  if (url.includes('/settings/models')) {
    if (method === 'GET' && url.match(/\/settings\/models$/)) {
      // GET /settings/models - 获取所有模型
      return ok(mockModels)
    } else if (method === 'GET' && url.includes('group=')) {
      // GET /settings/models?group=xxx - 获取指定分组模型
      const groupMatch = url.match(/group=([^&]+)/)
      if (groupMatch) {
        const group = groupMatch[1] as ModelGroup
        return ok(getMockModelsByGroup(group))
      }
    } else if (method === 'POST' && url.includes('group=')) {
      // POST /settings/models?group=xxx - 保存模型
      const groupMatch = url.match(/group=([^&]+)/)
      if (groupMatch) {
        const group = groupMatch[1] as ModelGroup
        const groupModels = getMockModelsByGroup(group)
        const existingIndex = groupModels.findIndex(m => m.name === requestData.name)

        if (existingIndex > -1) {
          // 更新现有模型
          groupModels[existingIndex] = { ...groupModels[existingIndex], ...requestData }
          return ok(groupModels[existingIndex])
        } else {
          // 新增模型
          groupModels.push(requestData as any)
          return ok(requestData)
        }
      }
    } else if (method === 'PUT' && url.includes('/default')) {
      // PUT /settings/models/:group/default?name=xxx - 设置默认模型
      const groupMatch = url.match(/\/settings\/models\/([^\/]+)\/default/)
      if (groupMatch) {
        const group = groupMatch[1] as ModelGroup
        const nameMatch = url.match(/name=([^&]+)/)
        if (nameMatch) {
          const name = nameMatch[1]
          const groupModels = getMockModelsByGroup(group)
          // 同组互斥设默认
          groupModels.forEach(m => {
            m.def = m.name === name
          })
          return ok({ success: true })
        }
      }
    } else if (method === 'DELETE' && url.includes('group=')) {
      // DELETE /settings/models?group=xxx&name=xxx - 删除模型
      const groupMatch = url.match(/group=([^&]+)/)
      const nameMatch = url.match(/name=([^&]+)/)
      if (groupMatch && nameMatch) {
        const group = groupMatch[1] as ModelGroup
        const name = nameMatch[1]
        const groupModels = getMockModelsByGroup(group)
        const index = groupModels.findIndex(m => m.name === name)
        if (index > -1) {
          groupModels.splice(index, 1)
          return ok({ success: true })
        }
        return { code: 404, message: '模型不存在', data: null }
      }
    }
  }

  if (url.includes('/settings/scenes')) {
    if (method === 'GET') {
      // GET /settings/scenes - 获取场景列表
      if (url.match(/^\/settings\/scenes$/) || url.match(/^\/settings\/scenes\?/)) {
        return ok(mockScenes)
      }
      // GET /settings/scenes/:id - 获取场景详情
      const detailMatch = url.match(/\/settings\/scenes\/([^\/]+)/)
      if (detailMatch) {
        const scene = mockScenes.find(s => s.id === detailMatch[1])
        if (scene) {
          return ok(scene)
        }
        return { code: 404, message: '场景不存在', data: null }
      }
    } else if (method === 'POST') {
      // POST /settings/scenes - 创建场景
      const newScene: Scene = {
        id: 'scene' + Date.now(),
        name: requestData.name || '',
        description: requestData.description || '',
        config: requestData.config || { chunk_size: 512, top_k: 5, system_prompt: '' }
      }
      mockScenes.push(newScene)
      return ok(newScene)
    } else if (method === 'PUT') {
      // PUT /settings/scenes/:id - 更新场景
      const updateMatch = url.match(/\/settings\/scenes\/([^\/]+)/)
      if (updateMatch) {
        const index = mockScenes.findIndex(s => s.id === updateMatch[1])
        if (index > -1) {
          mockScenes[index] = { ...mockScenes[index], ...requestData }
          return ok(mockScenes[index])
        }
        return { code: 404, message: '场景不存在', data: null }
      }
    } else if (method === 'DELETE') {
      // DELETE /settings/scenes/:id - 删除场景
      const deleteMatch = url.match(/\/settings\/scenes\/([^\/]+)/)
      if (deleteMatch) {
        const index = mockScenes.findIndex(s => s.id === deleteMatch[1])
        if (index > -1) {
          mockScenes.splice(index, 1)
          return ok({ success: true })
        }
        return { code: 404, message: '场景不存在', data: null }
      }
    }
  }
  // ========== 元素详情与上下文 ==========
  if (url.includes('/elements/') && url.includes('/context')) {
    const idMatch = url.match(/\/elements\/([^/?]+)/)
    if (idMatch) {
      const idx = mockElements.findIndex(e => e.element_id === idMatch[1])
      const start = Math.max(0, (idx > -1 ? idx : 0) - 1)
      return ok(mockElements.slice(start, start + 3))
    }
  }
  if (url.includes('/elements/')) {
    const idMatch = url.match(/\/elements\/([^/?]+)/)
    if (idMatch) {
      const element = mockElements.find(e => e.element_id === idMatch[1])
      return ok(element || mockElements[0])
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

