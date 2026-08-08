<script setup lang="ts">
import { onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import PageHeader from '@/components/common/PageHeader.vue'
import ConversationList from './components/ConversationList.vue'
import MessageList from './components/MessageList.vue'
import ChatInput from './components/ChatInput.vue'
import DocumentPicker from './components/DocumentPicker.vue'
import SceneSelector from './components/SceneSelector.vue'

const chatStore = useChatStore()

onMounted(() => {
  chatStore.loadConversations()
})
</script>

<template>
  <div class="chat-view">
    <!-- 左侧会话列表 -->
    <div class="left-panel">
      <ConversationList />
    </div>
    
    <!-- 中间对话区 -->
    <div class="center-panel">
      <PageHeader title="智能对话">
        <template #actions>
          <SceneSelector />
        </template>
      </PageHeader>
      
      <div class="chat-content">
        <MessageList />
      </div>
      
      <ChatInput />
    </div>
    
    <!-- 右侧文档选择 -->
    <div class="right-panel">
      <DocumentPicker />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.chat-view {
  height: 100%;
  display: flex;
  gap: 16px;
}

.left-panel {
  width: 260px;
  flex-shrink: 0;
}

.center-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px;
  
  .chat-content {
    flex: 1;
    min-height: 0;
    margin: 16px 0;
    background: #fff;
    border-radius: 8px;
    overflow: hidden;
  }
}

.right-panel {
  width: 280px;
  flex-shrink: 0;
}
</style>
