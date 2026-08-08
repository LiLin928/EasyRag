// 对话模块 Mock 数据
import type { Conversation, ChatMessage, Reference, Scene } from '@/types/chat'

// Mock 会话列表
export const mockConversations: Conversation[] = [
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

// Mock 历史消息
export const mockMessages: ChatMessage[] = [
  {
    id: 'msg1',
    role: 'user',
    content: '请分析这份标书的技术方案部分',
    ts: '2026-08-03 17:58:00'
  },
  {
    id: 'msg2',
    role: 'assistant',
    content: '根据标书内容，技术方案部分主要包含以下几个方面：\n\n## 1. 系统架构\n\n系统采用微服务架构设计，主要包括以下组件：\n- **前端服务**：基于 Vue 3 的 SPA 应用\n- **API 网关**：统一入口，负责认证和路由\n- **业务服务**：核心业务逻辑处理\n- **AI 服务**：大模型推理服务\n\n## 2. 技术选型\n\n| 层级 | 技术栈 | 说明 |\n|------|--------|------|\n| 前端 | Vue 3 + TypeScript | 现代化前端框架 |\n| 后端 | Python + FastAPI | 高性能异步框架 |\n| 数据库 | PostgreSQL | 关系型数据库 |\n| 缓存 | Redis | 内存数据库 |\n| AI | LangChain | LLM 应用框架 |\n\n## 3. 实施计划\n\n项目预计分三个阶段实施，总周期为6个月。',
    references: [
      {
        ref_id: 'ref1',
        element_id: 'e1',
        doc_title: '项目招标文件.pdf',
        node_title: '第二章 技术方案',
        content_preview: '系统架构采用微服务设计，支持横向扩展...',
        score: 0.92,
        type: 'text'
      },
      {
        ref_id: 'ref2',
        element_id: 'e2',
        doc_title: '项目招标文件.pdf',
        node_title: '第二章 技术方案',
        content_preview: '技术选型对比表...',
        score: 0.88,
        type: 'table'
      }
    ],
    trace: {
      trace_id: 'trace1',
      nav_ms: 150,
      retrieve_ms: 320,
      generate_ms: 2500,
      total_ms: 2970
    },
    usage: {
      prompt_tokens: 256,
      completion_tokens: 512,
      total_tokens: 768
    },
    ts: '2026-08-03 17:59:00'
  }
]

// Mock 引用
export const mockReferences: Reference[] = [
  {
    ref_id: 'ref1',
    element_id: 'e1',
    doc_title: '项目招标文件.pdf',
    node_title: '第二章 技术方案',
    content_preview: '系统架构采用微服务设计，支持横向扩展，具备高可用性和可维护性...',
    score: 0.92,
    type: 'text'
  },
  {
    ref_id: 'ref2',
    element_id: 'e2',
    doc_title: '项目招标文件.pdf',
    node_title: '第二章 技术方案',
    content_preview: '技术选型对比分析...',
    score: 0.88,
    type: 'table'
  }
]

// Mock 场景
export const mockScenes: Scene[] = [
  { id: 'general', name: '通用', desc: '通用对话模式' },
  { id: 'bidding', name: '招投标', desc: '招投标文档分析' },
  { id: 'contract', name: '合同', desc: '合同条款解读' },
  { id: 'tech', name: '技术', desc: '技术文档问答' }
]

// Mock SSE 回复文本
export const mockStreamText = '根据您的问题，我来为您分析：\n\n## 技术方案概述\n\n该项目的核心技术方案基于现代微服务架构，采用前后端分离的设计模式。前端使用 Vue 3 框架，后端采用 Python FastAPI，数据层使用 PostgreSQL 和 Redis。\n\n## 关键特性\n\n1. **高性能**：采用异步处理机制，支持高并发\n2. **可扩展**：微服务架构支持独立部署和扩展\n3. **安全可靠**：完善的认证授权机制\n\n## 实施建议\n\n建议按阶段推进，首先完成核心功能开发，然后进行集成测试，最后上线部署。'
