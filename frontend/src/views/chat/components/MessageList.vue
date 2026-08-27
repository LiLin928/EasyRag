<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '@/stores/chat'
import * as chatApi from '@/api/chat'
import ChatMessage from './ChatMessage.vue'
import type { ChatMessage as ChatMessageType } from '@/types/chat'

const chatStore = useChatStore()
const scrollRef = ref<HTMLElement | null>(null)

watch(
  () => chatStore.messages.length,
  () => {
    nextTick(() => {
      scrollToBottom()
    })
  }
)

watch(
  () => chatStore.streamBuffer,
  () => {
    nextTick(() => {
      scrollToBottom()
    })
  }
)

function scrollToBottom() {
  if (scrollRef.value) {
    scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  }
}

async function handleFeedback(msg: ChatMessageType, type: 'like' | 'dislike') {
  try {
    await chatApi.sendFeedback({ messageId: msg.id, type })
    ElMessage.success(type === 'like' ? '已点赞' : '已点踩')
  } catch (error) {
    ElMessage.error('反馈失败')
  }
}
</script>

<template>
  <el-scrollbar ref="scrollRef" class="message-list">
    <div class="messages-container">
      <ChatMessage
        v-for="msg in chatStore.messages"
        :key="msg.id"
        :data="msg"
        @feedback="(type) => handleFeedback(msg, type)"
      />
      
      <el-empty
        v-if="!chatStore.isStreaming && chatStore.messages.length === 0"
        description="开始对话吧"
      />
    </div>
  </el-scrollbar>
</template>

<style lang="scss" scoped>
.message-list {
  height: 100%;
}

.messages-container {
  padding: 16px;
  min-height: 100%;
}
</style>
