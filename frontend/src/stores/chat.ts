import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as chatApi from '@/api/chat'
import { useSSE } from '@/composables/useSSE'
import type { Conversation, ChatMessage, Reference, Phase, Scene } from '@/types/chat'

// 生成唯一 ID
function generateId() {
  return 'id-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9)
}

export const useChatStore = defineStore('chat', () => {
  // ========== 会话状态 ==========
  const conversations = ref<Conversation[]>([])
  const activeConversationId = ref<string>('')
  const messages = ref<ChatMessage[]>([])
  
  // ========== 流式状态 ==========
  const isStreaming = ref(false)
  const currentPhase = ref<Phase>('idle')
  const streamBuffer = ref('')
  
  // ========== 引用与追踪 ==========
  const references = ref<Reference[]>([])
  const traceInfo = ref<any>(null)
  
  // ========== 文档与场景 ==========
  const selectedDocIds = ref<string[]>([])
  const activeScene = ref('general')
  const scenes = ref<Scene[]>([])
  
  // ========== SSE 工具 ==========
  const { connect, abort } = useSSE()

  // ========== 计算属性 ==========
  const activeConversation = computed(() => {
    return conversations.value.find(c => c.id === activeConversationId.value)
  })

  // ========== 会话操作 ==========
  
  async function loadConversations() {
    conversations.value = await chatApi.getConversations()
  }

  async function createConversation(title?: string) {
    const conv = await chatApi.createConversation(title)
    conversations.value.unshift(conv)
    activeConversationId.value = conv.id
    messages.value = []
    return conv
  }

  async function deleteConversation(id: string) {
    await chatApi.deleteConversation(id)
    conversations.value = conversations.value.filter(c => c.id !== id)
    if (activeConversationId.value === id) {
      activeConversationId.value = conversations.value[0]?.id || ''
      if (activeConversationId.value) {
        loadHistory(activeConversationId.value)
      }
    }
  }

  async function loadHistory(convId: string) {
    messages.value = await chatApi.getHistory(convId)
  }

  function selectConversation(id: string) {
    activeConversationId.value = id
    loadHistory(id)
  }

  // ========== 发送消息 ==========

  async function sendMessage(question: string) {
    if (isStreaming.value) return

    // 添加用户消息
    const userMsg: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: question,
      ts: new Date().toISOString()
    }
    messages.value.push(userMsg)

    // 重置状态
    isStreaming.value = true
    currentPhase.value = 'parse'
    streamBuffer.value = ''
    references.value = []
    traceInfo.value = null

    // 创建助手消息占位
    const assistantMsg: ChatMessage = {
      id: generateId(),
      role: 'assistant',
      content: '',
      phase: 'parse',
      ts: new Date().toISOString()
    }
    messages.value.push(assistantMsg)

    // SSE 连接
    try {
      await connect(chatApi.getChatUrl(), {
        body: {
          conversation_id: activeConversationId.value,
          question,
          doc_ids: selectedDocIds.value,
          scene: activeScene.value
        },
        onEvent: (type, data) => {
          handleSSEEvent(assistantMsg.id, type, data)
        }
      })
    } catch (error) {
      console.error('SSE error:', error)
      assistantMsg.content = '抱歉，发生了错误，请重试。'
      isStreaming.value = false
      currentPhase.value = 'idle'
    }
  }

  function handleSSEEvent(msgId: string, type: string, data: any) {
    const msg = messages.value.find(m => m.id === msgId)
    if (!msg) return

    switch (type) {
      case 'phase':
        currentPhase.value = data.phase
        msg.phase = data.phase
        break

      case 'navigation':
        // 导航锚点，暂不处理
        break

      case 'references':
        references.value = data.refs || []
        msg.references = references.value
        break

      case 'token':
        streamBuffer.value += data.token
        msg.content = streamBuffer.value
        break

      case 'done':
        msg.usage = data.usage
        isStreaming.value = false
        currentPhase.value = 'idle'
        break

      case 'trace':
        traceInfo.value = data
        msg.trace = data
        break

      case 'error':
        msg.content = '错误：' + (data.message || '未知错误')
        isStreaming.value = false
        currentPhase.value = 'idle'
        break
    }
  }

  function stopGeneration() {
    abort()
    isStreaming.value = false
    currentPhase.value = 'idle'
  }

  // ========== 文档与场景 ==========

  function setSelectedDocs(ids: string[]) {
    selectedDocIds.value = ids
  }

  function setScene(scene: string) {
    activeScene.value = scene
  }

  async function loadScenes() {
    scenes.value = await chatApi.getScenes()
  }

  // ========== 反馈 ==========

  async function sendFeedback(messageId: string, type: 'like' | 'dislike') {
    await chatApi.sendFeedback({ messageId, type })
  }

  // ========== 重置 ==========

  function reset() {
    conversations.value = []
    activeConversationId.value = ''
    messages.value = []
    isStreaming.value = false
    currentPhase.value = 'idle'
    streamBuffer.value = ''
    references.value = []
    traceInfo.value = null
  }

  return {
    // 状态
    conversations,
    activeConversationId,
    messages,
    isStreaming,
    currentPhase,
    streamBuffer,
    references,
    traceInfo,
    selectedDocIds,
    activeScene,
    scenes,
    
    // 计算属性
    activeConversation,
    
    // 会话操作
    loadConversations,
    createConversation,
    deleteConversation,
    loadHistory,
    selectConversation,
    
    // 消息操作
    sendMessage,
    stopGeneration,
    
    // 文档与场景
    setSelectedDocs,
    setScene,
    loadScenes,
    
    // 反馈
    sendFeedback,
    
    // 重置
    reset
  }
})

