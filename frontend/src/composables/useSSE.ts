import { ref, onUnmounted } from 'vue'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { useAuthStore } from '@/stores/auth'

interface SSEOptions {
  body?: any
  onEvent?: (type: string, data: any) => void
  signal?: AbortSignal
}

// Mock SSE 模拟器：按契约事件顺序定时 emit
function simulateChatSSE(options: SSEOptions): Promise<void> {
  return new Promise(resolve => {
    const onEvent = options.onEvent
    if (!onEvent) {
      resolve()
      return
    }

    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    function emit(type: string, data: any) {
      if (cancelled) return
      onEvent!(type, data)
    }

    // 模拟回答文本（分 token 输出）
    const mockAnswer = '根据您提供的文档内容，以下是关键信息摘要：\n\n**核心要点：**\n\n1. 文档详细说明了项目的技术架构与实现方案。\n2. 重点关注数据安全与隐私保护的合规要求。\n3. 建议采用分层架构设计，确保系统可扩展性。\n\n**建议措施：**\n\n- 建立完善的文档版本管理机制\n- 定期进行安全审计与合规检查\n- 采用微服务架构提升系统灵活性\n\n如需进一步了解细节，请参考引用来源。'
    const tokens = mockAnswer.split('')

    // 四阶段事件序列
    const events: { delay: number; fn: () => void }[] = [
      // phase: parse
      { delay: 200, fn: () => emit('phase', { phase: 'parse' }) },
      // phase: navigate
      { delay: 600, fn: () => emit('phase', { phase: 'navigate' }) },
      // navigation
      { delay: 800, fn: () => emit('navigation', { anchors: ['p3', 'p7', 'p12'] }) },
      // phase: retrieve
      { delay: 1200, fn: () => emit('phase', { phase: 'retrieve' }) },
      // references
      {
        delay: 1800,
        fn: () =>
          emit('references', {
            refs: [
              { docId: 'doc1', docName: '技术架构白皮书.pdf', page: 3, score: 0.95, snippet: '系统采用分层架构设计，包含表现层、业务逻辑层和数据访问层...' },
              { docId: 'doc2', docName: '安全合规要求.docx', page: 7, score: 0.89, snippet: '所有敏感数据必须经过加密处理，满足等保三级要求...' },
              { docId: 'doc3', docName: '项目实施方案.md', page: 12, score: 0.82, snippet: '建议采用微服务架构，通过容器化部署实现弹性伸缩...' }
            ]
          })
      },
      // phase: generate
      { delay: 2200, fn: () => emit('phase', { phase: 'generate' }) }
    ]

    // 构建 token 事件
    tokens.forEach((tok, i) => {
      events.push({
        delay: 2400 + i * 40,
        fn: () => emit('token', { token: tok })
      })
    })

    // done + trace
    events.push({
      delay: 2400 + tokens.length * 40 + 200,
      fn: () =>
        emit('done', {
          usage: { prompt_tokens: 128, completion_tokens: tokens.length, total_tokens: 128 + tokens.length }
        })
    })
    events.push({
      delay: 2400 + tokens.length * 40 + 400,
      fn: () =>
        emit('trace', {
          phases: { parse: 200, navigate: 600, retrieve: 1200, generate: tokens.length * 40 },
          model: 'gpt-4',
          reranked: true
        })
    })

    // 按延迟顺序执行
    events.reduce((acc, ev) => {
      timer = setTimeout(() => {
        ev.fn()
        if (ev === events[events.length - 1]) {
          if (!cancelled) resolve()
        }
      }, acc + ev.delay)
      return acc + ev.delay
    }, 0)

    // 支持 abort
    const origSignal = options.signal
    if (origSignal) {
      origSignal.addEventListener('abort', () => {
        cancelled = true
        clearTimeout(timer)
        resolve()
      })
    }

    // 超时兜底
    setTimeout(() => {
      if (!cancelled) resolve()
    }, 2400 + tokens.length * 40 + 1000)
  })
}

export function useSSE() {
  const abortController = ref<AbortController | null>(null)
  const isStreaming = ref(false)

  async function connect(url: string, options: SSEOptions = {}) {
    const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

    // Mock 模式：使用模拟器替代真实 SSE
    if (USE_MOCK) {
      abortController.value = new AbortController()
      isStreaming.value = true
      try {
        await simulateChatSSE(options)
      } finally {
        isStreaming.value = false
      }
      return
    }

    // 真实 SSE
    const authStore = useAuthStore()
    abortController.value = new AbortController()
    isStreaming.value = true

    await fetchEventSource(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + authStore.token
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: options.signal || abortController.value.signal,
      onmessage(event) {
        if (options.onEvent) {
          try {
            const data = JSON.parse(event.data)
            options.onEvent(event.event || 'message', data)
          } catch (e) {
            options.onEvent(event.event || 'message', event.data)
          }
        }
      },
      onerror(error) {
        console.error('SSE error:', error)
        isStreaming.value = false
      },
      onclose() {
        isStreaming.value = false
      }
    })
  }

  function abort() {
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
      isStreaming.value = false
    }
  }

  onUnmounted(() => {
    abort()
  })

  return {
    connect,
    abort,
    isStreaming
  }
}

