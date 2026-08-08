// 知识库 Mock 数据
import type { KnowledgeBase, Document, TreeNode, DocElement, ParseTask } from '@/types/knowledge'

// Mock 知识库列表
export const mockKnowledgeBases: KnowledgeBase[] = [
  {
    id: 'kb1',
    name: '标书知识库',
    desc: '招投标相关文档，包括招标文件、投标文件、评标报告等',
    scene: 'bidding',
    docCount: 12,
    totalSize: '45.6 MB',
    createdAt: '2026-07-15 10:30:00',
    cover: '#409eff'
  },
  {
    id: 'kb2',
    name: '合同知识库',
    desc: '各类合同模板和已签署合同文档',
    scene: 'contract',
    docCount: 8,
    totalSize: '23.2 MB',
    createdAt: '2026-07-18 14:20:00',
    cover: '#67c23a'
  },
  {
    id: 'kb3',
    name: '通用知识库',
    desc: '公司通用文档、制度规范、操作手册等',
    scene: 'general',
    docCount: 15,
    totalSize: '89.4 MB',
    createdAt: '2026-07-20 09:15:00',
    cover: '#e6a23c'
  }
]

// Mock 文档列表
export const mockDocuments: Document[] = [
  {
    id: 'doc1',
    kbId: 'kb1',
    name: '项目招标文件.pdf',
    ext: 'pdf',
    size: '5.2 MB',
    pages: 48,
    mode: 'precision',
    status: 'done',
    elementCount: 256,
    createdAt: '2026-07-15 11:00:00'
  },
  {
    id: 'doc2',
    kbId: 'kb1',
    name: '投标响应书.docx',
    ext: 'docx',
    size: '3.8 MB',
    pages: 32,
    mode: 'fast',
    status: 'done',
    elementCount: 180,
    createdAt: '2026-07-16 09:30:00'
  },
  {
    id: 'doc3',
    kbId: 'kb1',
    name: '评标报告.pdf',
    ext: 'pdf',
    size: '2.1 MB',
    pages: 18,
    mode: 'precision',
    status: 'parsing',
    pct: 65,
    elementCount: 0,
    createdAt: '2026-07-17 14:20:00'
  },
  {
    id: 'doc4',
    kbId: 'kb2',
    name: '采购合同模板.docx',
    ext: 'docx',
    size: '1.5 MB',
    pages: 12,
    mode: 'fast',
    status: 'done',
    elementCount: 45,
    createdAt: '2026-07-18 15:00:00'
  }
]

// Mock 结构树
export const mockTree: TreeNode[] = [
  {
    node_id: 'n1',
    title: '第一章 项目概述',
    level: 1,
    summary: '项目背景和目标说明',
    element_count: 12,
    children: [
      {
        node_id: 'n1-1',
        title: '1.1 项目背景',
        level: 2,
        element_count: 5,
        children: []
      },
      {
        node_id: 'n1-2',
        title: '1.2 项目目标',
        level: 2,
        element_count: 7,
        children: []
      }
    ]
  },
  {
    node_id: 'n2',
    title: '第二章 技术方案',
    level: 1,
    summary: '系统架构和技术实现方案',
    element_count: 28,
    children: [
      {
        node_id: 'n2-1',
        title: '2.1 系统架构',
        level: 2,
        element_count: 10,
        children: []
      },
      {
        node_id: 'n2-2',
        title: '2.2 技术选型',
        level: 2,
        element_count: 18,
        children: []
      }
    ]
  },
  {
    node_id: 'n3',
    title: '第三章 项目实施',
    level: 1,
    element_count: 35,
    children: []
  }
]

// Mock 元素列表
export const mockElements: DocElement[] = [
  {
    element_id: 'e1',
    doc_title: '项目招标文件.pdf',
    type: 'text',
    content: '本项目旨在建设一个智能化的知识管理系统，实现知识的沉淀、共享和应用。系统需具备知识采集、知识组织、知识检索、知识推送等核心功能。',
    node_id: 'n1-1',
    node_title: '1.1 项目背景',
    page_number: 1,
    seq: 1
  },
  {
    element_id: 'e2',
    doc_title: '项目招标文件.pdf',
    type: 'table',
    content: JSON.stringify({
      headers: ['功能模块', '功能描述', '优先级'],
      rows: [
        ['知识采集', '支持多种格式文档的上传和解析', '高'],
        ['知识组织', '自动构建知识图谱和标签体系', '高'],
        ['知识检索', '智能语义检索和关联推荐', '高']
      ]
    }),
    node_id: 'n1-1',
    node_title: '1.1 项目背景',
    page_number: 2,
    seq: 2
  },
  {
    element_id: 'e3',
    doc_title: '项目招标文件.pdf',
    type: 'heading',
    content: '1.2 项目目标',
    node_id: 'n1-2',
    node_title: '1.2 项目目标',
    page_number: 3,
    seq: 1
  }
]

// Mock 解析任务
export const mockParseTask: ParseTask = {
  task_id: 'task1',
  doc_id: 'doc3',
  status: 'parsing',
  pct: 65
}
