<script setup lang="ts">
import { ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useChatStore } from '@/stores/chat'
import { useAgentStore } from '@/stores/agent'
import type { Agent } from '@/types/agent'

const chatStore = useChatStore()
const agentStore = useAgentStore()

// 智能体选择对话框状态
const agentDialogVisible = ref(false)
// 创建按钮加载状态
const isCreating = ref(false)

// 加载智能体列表
async function loadAgents() {
  await agentStore.loadAgents()
}

async function handleCreate() {
  // 防止重复点击
  if (isCreating.value) {
    console.log('[ConversationList] 正在创建中，忽略点击')
    return
  }
  
  // 先加载智能体列表
  await loadAgents()
  
  // 如果没有智能体，直接创建普通对话
  if (agentStore.agents.length === 0) {
    await createNormalConversation()
    return
  }
  
  // 显示智能体选择对话框
  agentDialogVisible.value = true
}

// 选择智能体创建对话
async function createWithAgent(agent: Agent) {
  if (isCreating.value) {
    console.log('[ConversationList] createWithAgent: 正在创建中，忽略')
    return
  }
  
  isCreating.value = true
  console.log('[ConversationList] createWithAgent:', agent.name)
  
  try {
    agentDialogVisible.value = false
    await chatStore.createConversation(`与 ${agent.name} 的对话`, agent.id)
  } finally {
    setTimeout(() => {
      isCreating.value = false
    }, 500)
  }
}

// 创建普通对话（不关联智能体）
async function createNormalConversation() {
  if (isCreating.value) {
    console.log('[ConversationList] createNormalConversation: 正在创建中，忽略')
    return
  }
  
  isCreating.value = true
  console.log('[ConversationList] createNormalConversation')
  
  try {
    agentDialogVisible.value = false
    await chatStore.createConversation('新对话')
  } finally {
    setTimeout(() => {
      isCreating.value = false
    }, 500)
  }
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

// 获取会话显示标题
function getConversationTitle(conv: any): string {
  // 如果有关联智能体，显示智能体名称
  if (conv.agentName) {
    return `🤖 ${conv.agentName}`
  }
  return conv.title
}
</script>

<template>
  <div class="conversation-list">
    <div class="list-header">
      <h3>会话列表</h3>
      <el-button 
        type="primary" 
        size="small" 
        icon="Plus" 
        :loading="isCreating"
        @click="handleCreate"
      >
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
            <div class="conv-title">{{ getConversationTitle(conv) }}</div>
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

    <!-- 智能体选择对话框 -->
    <el-dialog
      v-model="agentDialogVisible"
      title="选择智能体"
      width="500px"
      :close-on-click-modal="!isCreating"
      :close-on-press-escape="!isCreating"
    >
      <div class="agent-selector">
        <div class="agent-options">
          <!-- 普通对话选项 -->
          <div 
            class="agent-option normal-option"
            :class="{ disabled: isCreating }"
            @click="createNormalConversation"
          >
            <div class="agent-icon">
              <el-icon :size="24"><ChatDotRound /></el-icon>
            </div>
            <div class="agent-info">
              <div class="agent-name">普通对话</div>
              <div class="agent-desc">不关联智能体，使用通用配置</div>
            </div>
          </div>

          <el-divider>或选择智能体</el-divider>

          <!-- 智能体列表 -->
          <div 
            v-for="agent in agentStore.agents"
            :key="agent.id"
            class="agent-option"
            :class="{ disabled: isCreating }"
            @click="createWithAgent(agent)"
          >
            <div class="agent-icon">
              <el-avatar :size="40" icon="User" />
            </div>
            <div class="agent-info">
              <div class="agent-name">{{ agent.name }}</div>
              <div class="agent-desc">{{ agent.desc || '暂无描述' }}</div>
            </div>
            <div class="agent-enabled">
              <el-tag v-if="agent.enabled" size="small" type="success">已启用</el-tag>
              <el-tag v-else size="small" type="info">已禁用</el-tag>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
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

.el-empty {
  padding: 40px 0;
}

// 智能体选择对话框样式
.agent-selector {
  max-height: 400px;
  overflow-y: auto;
}

.agent-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.agent-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #ebeef5;

  &:hover:not(.disabled) {
    background: #f5f7fa;
    border-color: #409eff;
  }

  &.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  &.normal-option {
    .agent-icon {
      background: #409eff;
      color: #fff;
      width: 40px;
      height: 40px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
    }
  }
}

.agent-info {
  flex: 1;
  min-width: 0;

  .agent-name {
    font-size: 14px;
    font-weight: 500;
    color: #303133;
    margin-bottom: 4px;
  }

  .agent-desc {
    font-size: 12px;
    color: #909399;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.agent-enabled {
  flex-shrink: 0;
}
</style>
