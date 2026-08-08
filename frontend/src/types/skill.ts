// 技能模块类型定义

// 问答示例
export interface SkillExample {
  q: string  // 问题
  a: string  // 答案
}

// 关联脚本
export interface SkillScript {
  name: string    // 脚本名称
  content: string // 脚本代码内容
}

// 技能
export interface Skill {
  id: string
  ico: string                    // 图标
  name: string                   // 技能名称
  scope: 'builtin' | 'custom'    // 范围（内置/自定义）
  ver: string                    // 版本号
  desc: string                   // 描述
  trigger: string                // 触发条件
  prompt: string                 // 系统 Prompt
  tools: string[]                // 挂载的工具 ID 列表
  docs: string[]                 // 挂载的文档 ID 列表
  wfs: string[]                  // 挂载的工作流 ID 列表
  examples: SkillExample[]       // 问答示例
  scripts: SkillScript[]         // 关联脚本
  budget?: number                // Token 预算（可选）
  used?: number                  // 已用 Token（可选）
}
