/**
 * 智能体配置调试工具
 */

export interface AgentFormData {
  name: string
  desc: string
  model: string
  prompt: string
  temp: number
  maxtok: string
  tools: string[]
  docs: string[]
  wfs: string[]
  mcps: string[]
  skills: string[]
  enabled: boolean
}

/**
 * 调试智能体表单数据
 */
export function debugAgentForm(formData: AgentFormData, phase: string) {
  console.group(`[智能体调试] ${phase}`)
  console.log('完整表单数据:', JSON.parse(JSON.stringify(formData)))
  console.log('工具数量:', formData.tools?.length || 0, formData.tools)
  console.log('MCP数量:', formData.mcps?.length || 0, formData.mcps)
  console.log('技能数量:', formData.skills?.length || 0, formData.skills)
  console.log('文档数量:', formData.docs?.length || 0, formData.docs)
  console.log('工作流数量:', formData.wfs?.length || 0, formData.wfs)
  console.groupEnd()
}

/**
 * 验证智能体数据完整性
 */
export function validateAgentData(data: Partial<AgentFormData>): { valid: boolean; errors: string[] } {
  const errors: string[] = []
  const required: (keyof AgentFormData)[] = ['name', 'model']

  // 检查必填字段
  for (const field of required) {
    if (!data[field]) {
      errors.push(`缺少必填字段: ${field}`)
    }
  }

  // 检查数组字段
  const arrayFields: (keyof AgentFormData)[] = ['tools', 'mcps', 'skills', 'docs', 'wfs']
  for (const field of arrayFields) {
    if (data[field] && !Array.isArray(data[field])) {
      errors.push(`${field} 不是数组`)
    }
  }

  return {
    valid: errors.length === 0,
    errors
  }
}

/**
 * 深拷贝并验证数据
 */
export function safeCopyAgentData(data: Partial<AgentFormData>): AgentFormData {
  return {
    name: data.name || '',
    desc: data.desc || '',
    model: data.model || '',
    prompt: data.prompt || '',
    temp: data.temp ?? 0.7,
    maxtok: data.maxtok || '2048',
    tools: Array.isArray(data.tools) ? [...data.tools] : [],
    docs: Array.isArray(data.docs) ? [...data.docs] : [],
    wfs: Array.isArray(data.wfs) ? [...data.wfs] : [],
    mcps: Array.isArray(data.mcps) ? [...data.mcps] : [],
    skills: Array.isArray(data.skills) ? [...data.skills] : [],
    enabled: data.enabled ?? true
  }
}