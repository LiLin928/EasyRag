<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useChatStore } from '@/stores/chat'
import ChatMessage from './ChatMessage.vue'

const chatStore = useChatStore()
const scrollRef = ref<HTMLElement | null>(null)

// 监听消息变化，自动滚动到底部
watch(
  () => chatStore.messages.length,
  () => {
    nextTick(() => {
      scrollToBottom()
    })
  }
)

// 监听流式内容变化，自动滚动
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

function handleFeedback(_type: 'like' | 'dislike') {
  // TODO: 发送反馈
}
</script>

<template>
  <el-scrollbar ref="scrollRef" class="message-list">
    <div class="messages-container">
      <ChatMessage
        v-for="msg in chatStore.messages"
        :key="msg.id"
        :data="msg"
        @feedback="handleFeedback"
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

