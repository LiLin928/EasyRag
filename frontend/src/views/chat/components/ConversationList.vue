<script setup lang="ts">
import { ElMessageBox } from 'element-plus'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()

async function handleCreate() {
  await chatStore.createConversation('新对话')
}

async function handleDelete(id: string, e: Event) {
  e.stopPropagation()
  try {
    await ElMessageBox.confirm('确定要删除该会话吗？', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await chatStore.deleteConversation(id)
  } catch (error) {
    // 取消删除
  }
}

function handleSelect(id: string) {
  chatStore.selectConversation(id)
}

function formatTime(time: string) {
  const date = new Date(time)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前'
  return time.split(' ')[0]
}
</script>

<template>
  <div class="conversation-list">
    <div class="list-header">
      <h3>会话列表</h3>
      <el-button type="primary" size="small" icon="Plus" @click="handleCreate">
        新建
      </el-button>
    </div>
    
    <el-scrollbar class="list-scroll">
      <div class="list-content">
        <div
          v-for="conv in chatStore.conversations"
          :key="conv.id"
          class="conv-item"
          :class="{ active: conv.id === chatStore.activeConversationId }"
          @click="handleSelect(conv.id)"
        >
          <div class="conv-info">
            <div class="conv-title">{{ conv.title }}</div>
            <div class="conv-meta">
              <span>{{ conv.msgCount }} 条消息</span>
              <span>{{ formatTime(conv.lastTime) }}</span>
            </div>
          </div>
          <el-button
            class="delete-btn"
            link
            type="danger"
            size="small"
            icon="Delete"
            @click="(e: Event) => handleDelete(conv.id, e)"
          />
        </div>
        
        <el-empty v-if="chatStore.conversations.length === 0" description="暂无会话" />
      </div>
    </el-scrollbar>
  </div>
</template>

<style lang="scss" scoped>
.conversation-list {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #ebeef5;
  
  h3 {
    margin: 0;
    font-size: 14px;
    color: #303133;
  }
}

.list-scroll {
  flex: 1;
}

.list-content {
  padding: 8px;
}

.conv-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  margin-bottom: 4px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
  
  &:hover {
    background: #f5f7fa;
    
    .delete-btn {
      opacity: 1;
    }
  }
  
  &.active {
    background: #ecf5ff;
    
    .conv-title {
      color: #409eff;
    }
  }
  
  .conv-info {
    flex: 1;
    min-width: 0;
  }
  
  .conv-title {
    font-size: 14px;
    color: #303133;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .conv-meta {
    font-size: 12px;
    color: #909399;
    margin-top: 4px;
    display: flex;
    gap: 8px;
  }
  
  .delete-btn {
    opacity: 0;
    transition: opacity 0.2s;
  }
}
</style>

