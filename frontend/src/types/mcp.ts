// MCP 模块类型定义

// MCP 环境变量
export interface McpEnv {
  k: string  // key
  v: string  // value
}

// MCP 服务
export interface Mcp {
  id: string
  name: string
  tp: 'stdio' | 'SSE'  // 类型：stdio 或 SSE
  cmd: string  // 命令或 URL
  status: 'on' | 'off' | 'err'  // 状态：运行中/停止/错误
  toolCount: number  // 工具数量
  env: McpEnv[]  // 环境变量列表
  timeout: number  // 超时时间（秒）
  createdAt?: string
}

// MCP 测试结果
export interface McpTestResult {
  success: boolean
  toolCount: number
  tools?: string[]  // 工具名称列表
  error?: string
  duration: number
}
