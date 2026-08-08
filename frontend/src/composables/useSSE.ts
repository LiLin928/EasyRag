import { ref, onUnmounted } from 'vue'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import { useAuthStore } from '@/stores/auth'

interface SSEOptions {
  body?: any
  onEvent?: (type: string, data: any) => void
  signal?: AbortSignal
}

export function useSSE() {
  const abortController = ref<AbortController | null>(null)
  const isStreaming = ref(false)

  async function connect(url: string, options: SSEOptions = {}) {
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
