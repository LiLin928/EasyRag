import type { Workflow, Template, Execution, WfNode, WfEdge } from '@/types/workflow'

// ========== 模拟数据 ==========

export const mockWorkflows: Workflow[] = [
  {
    id: 'wf-1',
    name: '标准资料解析',
    description: '自动解析文档内容，提取关键信息',
    status: 'published',
    version: 3,
    nodes: [],
    edges: [],
    successRate: 95,
    lastRun: '2026-08-03 14:30:00',
    createdAt: '2026-07-15 10:00:00',
    updatedAt: '2026-08-01 09:00:00'
  },
  {
    id: 'wf-2',
    name: '文档摘要生成',
    description: '对多文档生成综合摘要',
    status: 'published',
    version: 2,
    nodes: [],
    edges: [],
    successRate: 88,
    lastRun: '2026-08-03 12:15:00',
    createdAt: '2026-07-20 14:00:00',
    updatedAt: '2026-07-28 16:00:00'
  },
  {
    id: 'wf-3',
    name: '多文档对比分析',
    description: '对比分析多个文档的差异',
    status: 'draft',
    version: 1,
    nodes: [],
    edges: [],
    createdAt: '2026-08-02 11:00:00',
    updatedAt: '2026-08-02 11:00:00'
  }
]

export const mockTemplates: Template[] = [
  {
    id: 'tpl-1',
    name: '标准资料审核流程',
    description: '适用于文档内容审核场景',
    source: 'official',
    tags: ['审核', '官方'],
    nodeCount: 5,
    useCount: 128,
    definition: { nodes: [], edges: [] }
  },
  {
    id: 'tpl-2',
    name: '文档摘要生成',
    description: '自动生成文档摘要',
    source: 'official',
    tags: ['摘要', '官方'],
    nodeCount: 4,
    useCount: 256,
    definition: { nodes: [], edges: [] }
  },
  {
    id: 'tpl-3',
    name: '联合要素提取',
    description: '从多文档中联合提取关键要素',
    source: 'community',
    tags: ['提取', '社区'],
    nodeCount: 6,
    useCount: 42,
    definition: { nodes: [], edges: [] }
  }
]

export const mockExecutions: Execution[] = [
  {
    id: 'exec-1',
    workflowId: 'wf-1',
    workflowName: '标准资料解析',
    status: 'success',
    trigger: 'manual',
    startTime: '2026-08-03 14:30:00',
    duration: 12500,
    nodeProgress: '5/5'
  },
  {
    id: 'exec-2',
    workflowId: 'wf-2',
    workflowName: '文档摘要生成',
    status: 'running',
    trigger: 'api',
    startTime: '2026-08-03 15:00:00',
    nodeProgress: '3/4'
  },
  {
    id: 'exec-3',
    workflowId: 'wf-1',
    workflowName: '标准资料解析',
    status: 'error',
    trigger: 'schedule',
    startTime: '2026-08-03 10:00:00',
    duration: 8000,
    nodeProgress: '4/5'
  },
  {
    id: 'exec-4',
    workflowId: 'wf-2',
    workflowName: '文档摘要生成',
    status: 'wait',
    trigger: 'agent',
    startTime: '2026-08-03 13:45:00',
    nodeProgress: '2/4'
  }
]

// 示例节点数据
export const mockNodes: WfNode[] = [
  {
    id: 'start', type: 'start', name: '开始', position: { x: 100, y: 100 },
    data: {
      rows: [],
      config: {
        input_variables: [
          { name: 'query', label: '用户问题', type: 'string', required: true }
        ]
      }
    }
  },
  {
    id: 'llm_1', type: 'llm', name: 'LLM 分析', position: { x: 350, y: 100 },
    data: {
      rows: [['模型', 'gpt-4']],
      config: {
        model: 'gpt-4',
        systemPrompt: '你是一个文档分析助手',
        temperature: 0.7,
        maxTokens: 2000,
        input_variables: [
          { name: 'query', source: '${start.query}' }
        ],
        output_variables: [
          { name: 'result' },
          { name: 'content' }
        ]
      }
    }
  },
  {
    id: 'cond_1', type: 'condition', name: '判断结果', position: { x: 600, y: 100 },
    data: {
      rows: [['条件', 'score > 0.8']],
      config: {
        expression: 'score > 0.8',
        trueLabel: '是',
        falseLabel: '否',
        input_variables: [
          { name: 'score', source: '${llm_1.result}' }
        ]
      }
    }
  },
  {
    id: 'tpl_1', type: 'template_render', name: '生成报告', position: { x: 850, y: 50 },
    data: {
      rows: [['模板', 'report.j2']],
      config: {
        template: '分析报告：{{content}}',
        input_variables: [
          { name: 'content', source: '${llm_1.content}' }
        ],
        output_variables: [
          { name: 'result' }
        ]
      }
    }
  },
  {
    id: 'var_1', type: 'variable_assign', name: '记录失败', position: { x: 850, y: 150 },
    data: {
      rows: [['变量', 'failed']],
      config: {
        varName: 'failed',
        varValue: 'true',
        input_variables: [
          { name: 'reason', source: '${llm_1.result}' }
        ]
      }
    }
  },
  {
    id: 'end', type: 'end', name: '结束', position: { x: 1100, y: 100 },
    data: {
      rows: [],
      config: {
        output_variables: [
          { name: 'report', source: '${tpl_1.result}' }
        ]
      }
    }
  }
]

export const mockEdges: WfEdge[] = [
  { id: 'e1', source: 'start', target: 'llm_1' },
  { id: 'e2', source: 'llm_1', target: 'cond_1' },
  { id: 'e3', source: 'cond_1', target: 'tpl_1', label: '是', sourceHandle: 'yes' },
  { id: 'e4', source: 'cond_1', target: 'var_1', label: '否', sourceHandle: 'no' },
  { id: 'e5', source: 'tpl_1', target: 'end' },
  { id: 'e6', source: 'var_1', target: 'end' }
]

// ========== Mock 辅助函数 ==========

export function handleWorkflowMock(url: string, method: string, data: any): any {
  // 工作流列表
  if (url.match(/\/workflows$/) && method === 'GET') {
    return { code: 0, data: mockWorkflows }
  }
  
  // 创建工作流
  if (url.match(/\/workflows$/) && method === 'POST') {
    const newWf: Workflow = {
      id: 'wf-' + Date.now(),
      name: data.name || '新流程',
      description: data.description,
      status: 'draft',
      version: 1,
      nodes: [],
      edges: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    }
    return { code: 0, data: newWf }
  }
  
  // 复制工作流
  if (url.match(/\/workflows\/.+\/duplicate$/) && method === 'POST') {
    const id = url.match(/\/workflows\/(.+)\/duplicate$/)?.[1]
    const original = mockWorkflows.find(w => w.id === id)
    if (!original) return { code: 404, message: 'Not found' }
    const copy: Workflow = {
      ...original,
      id: 'wf-' + Date.now(),
      name: original.name + ' (副本)',
      status: 'draft',
      version: 1,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    }
    return { code: 0, data: copy }
  }
  
  // 删除工作流
  if (url.match(/\/workflows\/[^/]+$/) && method === 'DELETE') {
    return { code: 0 }
  }
  
  // 获取工作流详情
  if (url.match(/\/workflows\/[^/]+$/) && method === 'GET') {
    const id = url.match(/\/workflows\/(.+)$/)?.[1]
    const wf = mockWorkflows.find(w => w.id === id)
    if (!wf) return { code: 404, message: 'Not found' }
    // 补充节点数据
    return { code: 0, data: { ...wf, nodes: mockNodes, edges: mockEdges } }
  }
  
  // 更新工作流
  if (url.match(/\/workflows\/[^/]+$/) && method === 'PUT') {
    const id = url.match(/\/workflows\/(.+)$/)?.[1]
    const wf = mockWorkflows.find(w => w.id === id)
    if (!wf) return { code: 404, message: 'Not found' }
    Object.assign(wf, data, { updatedAt: new Date().toISOString() })
    return { code: 0, data: wf }
  }
  
  // 发布工作流
  if (url.match(/\/workflows\/.+\/publish$/) && method === 'POST') {
    const id = url.match(/\/workflows\/(.+)\/publish$/)?.[1]
    const wf = mockWorkflows.find(w => w.id === id)
    if (!wf) return { code: 404, message: 'Not found' }
    wf.status = 'published'
    wf.version++
    return { code: 0, data: wf }
  }
  
  // 模板列表
  if (url.match(/\/templates$/) && method === 'GET') {
    return { code: 0, data: mockTemplates }
  }
  
  // 从模板创建
  if (url.match(/\/templates\/.+\/instantiate$/) && method === 'POST') {
    const tplId = url.match(/\/templates\/(.+)\/instantiate$/)?.[1]
    const tpl = mockTemplates.find(t => t.id === tplId)
    if (!tpl) return { code: 404, message: 'Not found' }
    const newWf: Workflow = {
      id: 'wf-' + Date.now(),
      name: data.name || tpl.name,
      description: tpl.description,
      status: 'draft',
      version: 1,
      nodes: [],
      edges: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    }
    return { code: 0, data: newWf }
  }
  
  // 执行历史
  if (url.match(/\/executions$/) && method === 'GET') {
    return { code: 0, data: mockExecutions }
  }
  
  // 执行工作流
  if (url.match(/\/workflows\/.+\/execute$/) && method === 'POST') {
    return { code: 0, data: { executionId: 'exec-' + Date.now() } }
  }
  
  return null
}


