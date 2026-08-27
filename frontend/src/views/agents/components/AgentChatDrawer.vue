<script setup lang="ts">
import { ref, nextTick, onUnmounted } from 'vue'
import { useSSE } from '@/composables/useSSE'
import { getChatUrl } from '@/api/chat'
import type { Agent } from '@/types/agent'
import type { ChatMessage } from '@/types/chat'
import { renderMarkdown } from '@/composables/useMarkdown'

interface Props {
  visible: boolean
  agent: Agent
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:visible': [visible: boolean]
}>()

const { connect, abort, isStreaming } = useSSE()

const messages = ref<ChatMessage[]>([])
const inputMessage = ref('')
const messageContainer = ref<HTMLElement>()

// 创建用户消息
function createUserMessage(content: string): ChatMessage {
  return {
    id: 'msg-' + Date.now(),
    role: 'user',
    content,
    ts: new Date().toISOString()
  }
}

// 创建助手消息
function createAssistantMessage(): ChatMessage {
  return {
    id: 'msg-' + Date.now() + 1,
    role: 'assistant',
    content: '',
    phase: 'idle',
    ts: new Date().toISOString()
  }
}

// 发送消息
async function sendMessage() {
  if (!inputMessage.value.trim() || isStreaming.value) return

  const userMessage = createUserMessage(inputMessage.value)
  const assistantMessage = createAssistantMessage()

  messages.value.push(userMessage)
  messages.value.push(assistantMessage)

  const userContent = inputMessage.value
  inputMessage.value = ''

  await scrollToBottom()

  // 使用 SSE 发送消息
  await connect(getChatUrl(), {
    body: {
      agentId: props.agent.id,
      message: userContent
    },
    onEvent: (event, data) => {
      handleSSEEvent(assistantMessage, event, data)
    }
  })
}

// 处理 SSE 事件
function handleSSEEvent(message: ChatMessage, event: string, data: any) {
  switch (event) {
    case 'phase':
      // 更新阶段
      if (message) {
        message.phase = data.phase
      }
      break

    case 'token':
      // 追加文本
      if (message) {
        message.content = (message.content || '') + data.text
      }
      break

    case 'done':
      // 完成
      if (message) {
        message.phase = 'idle'
        message.trace = data.trace
        message.usage = data.usage
      }
      break

    case 'error':
      // 错误
      if (message) {
        message.phase = 'idle'
        message.content = '抱歉，发生了错误：' + (data.error || '未知错误')
      }
      break
  }

  nextTick(() => {
    scrollToBottom()
  })
}

// 滚动到底部
async function scrollToBottom() {
  await nextTick()
  if (messageContainer.value) {
    messageContainer.value.scrollTop = messageContainer.value.scrollHeight
  }
}

// 停止生成
function stopGeneration() {
  abort()
}

// 关闭抽屉
function handleClose() {
  abort()
  emit('update:visible', false)
}

// 组件卸载时清理
onUnmounted(() => {
  abort()
})
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="`与 ${agent.name} 对话`"
    width="700px"
    :close-on-click-modal="false"
    @update:model-value="handleClose"
  >
    <div class="chat-drawer">
      <!-- 消息列表 -->
      <div ref="messageContainer" class="messages-container">
        <div
          v-for="message in messages"
          :key="message.id"
          class="chat-message"
          :class="message.role"
        >
          <div class="message-avatar">
            <el-avatar v-if="message.role === 'user'" :size="32" icon="User" />
            <el-avatar v-else :size="32" style="background: #409eff">
              <el-icon><ChatDotRound /></el-icon>
            </el-avatar>
          </div>

          <div class="message-content">
            <div v-if="message.phase && message.phase !== 'idle'" class="phase-indicator">
              <el-tag size="small" type="info">
                {{ message.phase === 'parse' ? '解析中' : '' }}
                {{ message.phase === 'navigate' ? '导航中' : '' }}
                {{ message.phase === 'retrieve' ? '检索中' : '' }}
                {{ message.phase === 'generate' ? '生成中' : '' }}
              </el-tag>
            </div>

            <div class="content-text" v-html="renderMarkdown(message.content || '') || '正在思考...'"></div>

            <div v-if="message.trace" class="message-footer">
              <span class="trace-info">
                导航 {{ message.trace.nav_ms }}ms ·
                检索 {{ message.trace.retrieve_ms }}ms ·
                生成 {{ message.trace.generate_ms }}ms
              </span>
              <span v-if="message.usage" class="usage-info">
                Token: {{ message.usage.total_tokens }}
              </span>
            </div>
          </div>
        </div>

        <div v-if="messages.length === 0" class="empty-chat">
          <el-icon :size="48" color="#c0c4cc"><ChatDotRound /></el-icon>
          <p>开始与 {{ agent.name }} 对话吧</p>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <div v-if="isStreaming" class="streaming-controls">
          <el-button size="small" type="warning" @click="stopGeneration">
            停止生成
          </el-button>
        </div>
        <div class="input-wrapper">
          <el-input
            v-model="inputMessage"
            type="textarea"
            :rows="3"
            placeholder="输入消息..."
            :disabled="isStreaming"
            @keydown.enter.ctrl="sendMessage"
          />
          <el-button
            type="primary"
            :disabled="!inputMessage.trim() || isStreaming"
            @click="sendMessage"
          >
            发送 (Ctrl+Enter)
          </el-button>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<style lang="scss" scoped>
.chat-drawer {
  height: 600px;
  display: flex;
  flex-direction: column;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 16px;
}

.chat-message {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;

  &.user {
    .message-content {
      background: #ecf5ff;
    }
  }

  &.assistant {
    .message-content {
      background: #fff;
    }
  }
}

.message-avatar {
  flex-shrink: 0;
}

.message-content {
  flex: 1;
  min-width: 0;
  padding: 12px 16px;
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.phase-indicator {
  margin-bottom: 8px;
}

.content-text {
  font-size: 14px;
  line-height: 1.6;
  color: #303133;

  :deep(h1), :deep(h2), :deep(h3) {
    margin: 16px 0 8px;
  }

  :deep(ul), :deep(ol) {
    padding-left: 20px;
  }

  :deep(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;

    th, td {
      border: 1px solid #ebeef5;
      padding: 8px 12px;
      text-align: left;
    }

    th {
      background: #f5f7fa;
    }
  }

  :deep(p) {
    margin-bottom: 8px;
  }

  &:last-child {
    margin-bottom: 0;
  }
}

.message-footer {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #ebeef5;
  font-size: 12px;
  color: #909399;
}

.empty-chat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;

  p {
    margin-top: 12px;
  }
}

.input-area {
  border-top: 1px solid #f0f0f0;
  padding-top: 16px;
}

.streaming-controls {
  margin-bottom: 8px;
}

.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-wrapper .el-button {
  align-self: flex-end;
}
</style>
