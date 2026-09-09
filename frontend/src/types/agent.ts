// 智能体模块类型定义

// 智能体
export interface Agent {
  id: string
  name: string                    // 智能体名称
  desc: string                    // 描述
  model: string                   // 模型
  prompt: string                  // 系统提示词
  temp: number                    // 温度（0-2）
  maxtok: string                  // 最大 Token 数
  tools: string[]                 // 挂载的工具 ID 列表
  docs: string[]                  // 挂载的文档 ID 列表
  wfs: string[]                   // 挂载的工作流 ID 列表
  mcps: string[]                  // 挂载的 MCP 服务 ID 列表
  skills: string[]                // 挂载的技能 ID 列表
  enabled: boolean                // 是否启用
  lastActive: string              // 最近活跃时间
  createdAt?: string             // 创建时间
}
