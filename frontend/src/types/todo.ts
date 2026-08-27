// 待办中心模块类型定义

// 表单字段类型
export interface FormField {
  key: string                              // 字段标识
  label: string                             // 字段标签
  type: 'text' | 'textarea' | 'select' | 'radio' | 'number' | 'upload'  // 字段类型
  required?: boolean                        // 是否必填
  options?: { label: string; value: string }[]  // 选项（用于 select/radio）
}

// 导出别名给 DynamicForm 使用
export type TodoFormField = FormField

// 待办事项
export interface Todo {
  id: string                                // 待办ID
  title: string                             // 标题
  source: string                            // 来源（流程 · 节点）
  status: 'pending' | 'done' | 'rejected'   // 状态
  submittedAt?: string                      // 提交时间
  cd?: boolean                              // 是否已超时
  deadline?: number                         // 剩余秒数
  formSchema: FormField[]                   // 表单结构
  formData?: Record<string, unknown>        // 表单数据
}