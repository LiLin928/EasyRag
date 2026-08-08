<script setup lang="ts">
import { ref } from 'vue'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()

const inputText = ref('')

function handleSend() {
  const text = inputText.value.trim()
  if (!text || chatStore.isStreaming) return
  
  chatStore.sendMessage(text)
  inputText.value = ''
}

function handleKeyDown(e: Event | KeyboardEvent) {
  if ((e as KeyboardEvent).key === 'Enter' && !(e as KeyboardEvent).shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function handleStop() {
  chatStore.stopGeneration()
}
</script>

<template>
  <div class="chat-input">
    <div class="input-wrapper">
      <el-input
        v-model="inputText"
        type="textarea"
        placeholder="输入问题，按 Enter 发送，Shift + Enter 换行"
        :autosize="{ minRows: 1, maxRows: 4 }"
        :disabled="chatStore.isStreaming"
        @keydown="handleKeyDown"
      />
      
      <div class="input-actions">
        <span v-if="chatStore.selectedDocIds.length > 0" class="doc-hint">
          基于 {{ chatStore.selectedDocIds.length }} 篇文档
        </span>
        
        <el-button
          v-if="chatStore.isStreaming"
          type="danger"
          icon="VideoPause"
          @click="handleStop"
        >
          停止
        </el-button>
        <el-button
          v-else
          type="primary"
          icon="Promotion"
          :disabled="!inputText.trim()"
          @click="handleSend"
        >
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.chat-input {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.05);
}

.input-wrapper {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  
  :deep(.el-textarea) {
    flex: 1;
  }
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  
  .doc-hint {
    font-size: 12px;
    color: #909399;
  }
}
</style>


