// 系统设置 Mock 数据
import type { ModelGroup, ModelDef, Scene } from '@/types/settings'

// ========== 模型数据 ==========

// Mock LLM 模型
export const mockLlmModels: ModelDef[] = [
  {
    name: 'qwen2.5-72b-instruct',
    prov: 'dashscope',
    use: 'qa',
    temp: 0.7,
    ctx: '32768',
    def: true,
    url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    key: 'sk-xxxxxxxxxxxx',
    params: {
      top_p: '0.9',
      max_tokens: '4096'
    }
  },
  {
    name: 'qwen2.5-7b-instruct',
    prov: 'dashscope',
    use: 'summary',
    temp: 0.5,
    ctx: '32768',
    def: false,
    url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    key: 'sk-xxxxxxxxxxxx',
    params: {
      top_p: '0.9',
      max_tokens: '2048'
    }
  },
  {
    name: 'gpt-4o-mini',
    prov: 'openai',
    use: 'rewrite',
    temp: 0.3,
    ctx: '128000',
    def: false,
    url: 'https://api.openai.com/v1',
    key: 'sk-xxxxxxxxxxxx',
    params: {
      top_p: '0.95',
      max_tokens: '1024'
    }
  }
]

// Mock Embedding 模型
export const mockEmbedModels: ModelDef[] = [
  {
    name: 'text-embedding-v3',
    prov: 'dashscope',
    use: 'retrieval',
    dim: '1024',
    def: true,
    url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    key: 'sk-xxxxxxxxxxxx',
    params: {}
  },
  {
    name: 'bge-m3',
    prov: 'ollama',
    use: 'retrieval',
    dim: '1024',
    def: false,
    url: 'http://localhost:11434/v1',
    key: '',
    params: {}
  }
]

// Mock Rerank 模型
export const mockRerankModels: ModelDef[] = [
  {
    name: 'gte-rerank-v2',
    prov: 'dashscope',
    use: 'rerank',
    def: true,
    url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    key: 'sk-xxxxxxxxxxxx',
    params: {
      top_n: '5'
    }
  },
  {
    name: 'bge-reranker-v2-m3',
    prov: 'ollama',
    use: 'rerank',
    def: false,
    url: 'http://localhost:11434/v1',
    key: '',
    params: {
      top_n: '3'
    }
  }
]

// 按分组获取模型
export function getMockModelsByGroup(group: ModelGroup): ModelDef[] {
  switch (group) {
    case 'llm':
      return mockLlmModels
    case 'embed':
      return mockEmbedModels
    case 'rerank':
      return mockRerankModels
    default:
      return []
  }
}

// 获取所有模型
export const mockModels: Record<ModelGroup, ModelDef[]> = {
  llm: mockLlmModels,
  embed: mockEmbedModels,
  rerank: mockRerankModels
}

// ========== 场景数据 ==========

export const mockScenes: Scene[] = [
  {
    id: 'scene1',
    name: '通用问答',
    description: '适用于大多数通用知识问答场景，提供准确详细的回答',
    config: {
      chunk_size: 512,
      top_k: 5,
      system_prompt: '你是一个专业的智能助手，负责基于提供的知识库内容回答用户问题。请根据参考内容给出准确、详细的回答，如果无法从参考内容中找到答案，请明确告知用户。'
    }
  },
  {
    id: 'scene2',
    name: '标书文档',
    description: '专门用于处理标书、招标文件等正式文档的问答',
    config: {
      chunk_size: 1024,
      top_k: 3,
      system_prompt: '你是一个专业的标书文档分析助手，负责从标书和招标文件中提取关键信息。请严格按照文档内容回答，保持专业性和准确性，对不确定的信息请明确标注。'
    }
  },
  {
    id: 'scene3',
    name: '技术支持',
    description: '面向技术支持和故障排查场景的快速响应',
    config: {
      chunk_size: 256,
      top_k: 8,
      system_prompt: '你是一个技术支持专家，负责帮助用户解决技术问题和故障排查。请提供清晰、可操作的解决方案，必要时可以建议用户联系人工支持。'
    }
  }
]
