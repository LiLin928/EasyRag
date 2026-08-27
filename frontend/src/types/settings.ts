// 系统设置模块类型定义

// 模型分组
export type ModelGroup = 'llm' | 'embed' | 'rerank'

// 模型定义
export interface ModelDef {
  name: string                              // 模型名称
  prov: string                              // 供应商：DashScope / OpenAI 兼容 / 本地 Ollama / Azure OpenAI / 自建 vLLM
  use: string                               // 用途：按分组动态选项
  temp?: number                             // 温度（LLM 组）
  ctx?: string                              // 上下文长度
  dim?: string                              // 维度（Embedding 组）
  def?: boolean                             // 是否默认（同组单选）
  url?: string                              // API 地址
  key?: string                              // 密钥（掩码显示）
  params: Record<string, string>            // 动态参数（top_p/max_tokens 等）
}

// 场景预设
export interface Scene {
  id: string                                // 场景 ID
  name: string                              // 场景名称
  description: string                      // 场景描述
  config: {
    chunk_size: number                      // 分块大小
    top_k: number                           // 召回数量
    system_prompt: string                   // 系统提示词
  }
}

// 供应商选项
export const PROVIDERS = [
  { label: 'DashScope (阿里云)', value: 'dashscope' },
  { label: 'OpenAI 兼容', value: 'openai' },
  { label: '本地 Ollama', value: 'ollama' },
  { label: 'Azure OpenAI', value: 'azure' },
  { label: '自建 vLLM', value: 'vllm' }
] as const

// 用途选项（按分组）
export const USE_OPTIONS = {
  llm: [
    { label: '答疑生成', value: 'qa' },
    { label: '快速摘要', value: 'summary' },
    { label: '问题改写', value: 'rewrite' }
  ],
  embed: [
    { label: '向量召回', value: 'retrieval' }
  ],
  rerank: [
    { label: '精排', value: 'rerank' }
  ]
} as const
