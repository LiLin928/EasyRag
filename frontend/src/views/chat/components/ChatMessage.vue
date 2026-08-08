<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '@/types/chat'
import PhaseIndicator from './PhaseIndicator.vue'
import ReferenceCard from './ReferenceCard.vue'

interface Props {
  data: ChatMessage
}

const props = defineProps<Props>()

const emit = defineEmits<{
  feedback: [type: 'like' | 'dislike']
  expandRef: [elementId: string]
}>()

const isUser = computed(() => props.data.role === 'user')
const isStreaming = computed(() => props.data.phase && props.data.phase !== 'idle' && !props.data.trace)
</script>

<template>
  <div class="chat-message" :class="data.role">
    <div class="message-avatar">
      <el-avatar v-if="isUser" :size="32" icon="User" />
      <el-avatar v-else :size="32" style="background: #409eff">
        <el-icon><ChatDotRound /></el-icon>
      </el-avatar>
    </div>
    
    <div class="message-content">
      <!-- 阶段指示器 -->
      <PhaseIndicator
        v-if="isStreaming && data.phase"
        :phase="data.phase"
      />
      
      <!-- 消息内容 -->
      <div class="content-text" v-html="data.content || '正在思考...'"></div>
      
      <!-- 引用列表 -->
      <div v-if="data.references && data.references.length > 0" class="references">
        <div class="refs-header">
          <el-icon><Collection /></el-icon>
          <span>引用来源</span>
        </div>
        <ReferenceCard
          v-for="(ref, index) in data.references"
          :key="ref.ref_id"
          :data="ref"
          :index="index"
          @expand="(id) => emit('expandRef', id)"
        />
      </div>
      
      <!-- 底部信息 -->
      <div v-if="!isStreaming && data.trace" class="message-footer">
        <span class="trace-info">
          导航 {{ data.trace.nav_ms }}ms · 检索 {{ data.trace.retrieve_ms }}ms · 生成 {{ data.trace.generate_ms }}ms
        </span>
        <span v-if="data.usage" class="usage-info">
          Token: {{ data.usage.total_tokens }}
        </span>
        
        <!-- 反馈按钮 -->
        <div v-if="!isUser" class="feedback-actions">
          <el-button size="small" text @click="emit('feedback', 'like')">
            <el-icon><CaretTop /></el-icon>
          </el-button>
          <el-button size="small" text @click="emit('feedback', 'dislike')">
            <el-icon><CaretBottom /></el-icon>
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.chat-message {
  display: flex;
  gap: 12px;
  padding: 16px 0;
  
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
  padding: 16px;
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
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
}

.references {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
  
  .refs-header {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: #909399;
    margin-bottom: 8px;
  }
}

.message-footer {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
  font-size: 12px;
  color: #909399;
  
  .feedback-actions {
    margin-left: auto;
    display: flex;
    gap: 4px;
  }
}
</style>
