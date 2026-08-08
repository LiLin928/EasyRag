// 工具模块类型定义

// 工具参数
export interface ToolParam {
  n: string  // 参数名
  t: string  // 参数类型 (string/number/boolean/object/array)
  d: string  // 默认值
}

// 工具鉴权
export interface ToolAuth {
  mode: 'none' | 'apikey' | 'bearer'  // 鉴权模式
  key: string                          // 密钥（掩码显示）
}

// 工具
export interface Tool {
  id: string
  name: string
  type: 'HTTP' | '内置' | 'Python'
  desc: string
  sig: string                    // 签名（函数签名）
  enabled: boolean
  params: ToolParam[]
  auth: ToolAuth
  createdAt?: string
}

// 工具测试参数（动态测试参数容器，值类型由 param.t 运行时决定）
export interface ToolTestArgs {
  [key: string]: any
}

// 工具测试结果
export interface ToolTestResult {
  success: boolean
  data?: unknown
  error?: string
  duration: number
}
