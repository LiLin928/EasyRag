// 待办 Mock 数据
import type { Todo } from '@/types/todo'

// Mock 待办列表
export const mockTodos: Todo[] = [
  {
    id: 'todo1',
    title: '标书资质分析审批',
    source: '标书审核流程 · 人工审核节点',
    status: 'pending',
    deadline: 85200,  // 约23小时40分钟
    cd: false,
    formSchema: [
      {
        key: 'approval_opinion',
        label: '审批意见',
        type: 'textarea',
        required: true
      },
      {
        key: 'approval_result',
        label: '审批结果',
        type: 'radio',
        required: true,
        options: [
          { label: '通过', value: 'approved' },
          { label: '驳回', value: 'rejected' }
        ]
      },
      {
        key: 'priority',
        label: '优先级',
        type: 'select',
        required: false,
        options: [
          { label: '高', value: 'high' },
          { label: '中', value: 'medium' },
          { label: '低', value: 'low' }
        ]
      }
    ]
  },
  {
    id: 'todo2',
    title: '数据格式确认',
    source: '数据清洗流程 · 格式校验节点',
    status: 'pending',
    deadline: 3600,  // 1小时
    cd: false,
    formSchema: [
      {
        key: 'data_format',
        label: '数据格式',
        type: 'select',
        required: true,
        options: [
          { label: 'JSON', value: 'json' },
          { label: 'CSV', value: 'csv' },
          { label: 'XML', value: 'xml' }
        ]
      },
      {
        key: 'encoding',
        label: '编码格式',
        type: 'text',
        required: false
      },
      {
        key: 'row_limit',
        label: '行数限制',
        type: 'number',
        required: false
      }
    ]
  },
  {
    id: 'todo3',
    title: '模型参数配置确认',
    source: '模型训练流程 · 参数调优节点',
    status: 'pending',
    deadline: 18000,  // 5小时
    cd: false,
    formSchema: [
      {
        key: 'learning_rate',
        label: '学习率',
        type: 'number',
        required: true
      },
      {
        key: 'batch_size',
        label: '批大小',
        type: 'number',
        required: true
      },
      {
        key: 'optimizer',
        label: '优化器',
        type: 'select',
        required: true,
        options: [
          { label: 'Adam', value: 'adam' },
          { label: 'SGD', value: 'sgd' },
          { label: 'AdamW', value: 'adamw' }
        ]
      },
      {
        key: 'notes',
        label: '备注',
        type: 'textarea',
        required: false
      }
    ]
  },
  {
    id: 'todo4',
    title: 'API 接口文档审核',
    source: 'API 发布流程 · 文档审核节点',
    status: 'done',
    submittedAt: '2026-08-07 15:30:00',
    formSchema: [
      {
        key: 'doc_quality',
        label: '文档质量评分',
        type: 'select',
        required: true,
        options: [
          { label: '优秀', value: 'excellent' },
          { label: '良好', value: 'good' },
          { label: '需改进', value: 'improvement' }
        ]
      },
      {
        key: 'comments',
        label: '审核意见',
        type: 'textarea',
        required: false
      }
    ],
    formData: {
      doc_quality: 'excellent',
      comments: '文档结构清晰，示例完整'
    }
  },
  {
    id: 'todo5',
    title: '预算申请审批',
    source: '资源申请流程 · 财务审批节点',
    status: 'rejected',
    submittedAt: '2026-08-06 10:15:00',
    formSchema: [
      {
        key: 'budget_amount',
        label: '预算金额',
        type: 'number',
        required: true
      },
      {
        key: 'justification',
        label: '申请理由',
        type: 'textarea',
        required: true
      },
      {
        key: 'supporting_docs',
        label: '支持文档',
        type: 'upload',
        required: false
      }
    ],
    formData: {
      budget_amount: 50000,
      justification: '购买服务器用于模型训练'
    }
  }
]

// 模拟提交待办（修改状态为 done + 记录提交时间）
export function submitMockTodo(id: string, formData: Record<string, unknown>): Todo | null {
  const todo = mockTodos.find(t => t.id === id)
  if (todo) {
    todo.status = 'done'
    todo.submittedAt = new Date().toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    }).replace(/\//g, '-')
    todo.formData = formData
    todo.deadline = undefined  // 清除倒计时
    todo.cd = false

    // 模拟触发工作流 resumed 事件
    console.log('[Mock] 触发工作流 execution_resumed, todoId=', id)

    return todo
  }
  return null
}

// 模拟驳回待办
export function rejectMockTodo(id: string): Todo | null {
  const todo = mockTodos.find(t => t.id === id)
  if (todo) {
    todo.status = 'rejected'
    todo.submittedAt = new Date().toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    }).replace(/\//g, '-')
    todo.deadline = undefined  // 清除倒计时
    todo.cd = false
    return todo
  }
  return null
}