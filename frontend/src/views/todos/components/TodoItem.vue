<script setup lang="ts">
import { computed } from 'vue'
import StatusChip from '@/components/common/StatusChip.vue'
import CountdownBadge from './CountdownBadge.vue'
import type { Todo } from '@/types/todo'

interface Props {
  data: Todo
  active?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  active: false
})

const emit = defineEmits<{
  select: [id: string]
}>()

// 状态映射到 StatusChip 类型
const statusType = computed(() => {
  switch (props.data.status) {
    case 'pending':
      return 'wait'
    case 'done':
      return 'ok'
    case 'rejected':
      return 'err'
    default:
      return 'gray'
  }
})

// 状态文本
const statusText = computed(() => {
  switch (props.data.status) {
    case 'pending':
      return '待处理'
    case 'done':
      return '已完成'
    case 'rejected':
      return '已驳回'
    default:
      return '未知'
  }
})

function handleClick() {
  emit('select', props.data.id)
}
</script>

<template>
  <div
    class="todo-item"
    :class="{ active }"
    @click="handleClick"
  >
    <div class="todo-main">
      <div class="todo-header">
        <h4 class="todo-title">{{ data.title }}</h4>
        <StatusChip :type="statusType" :label="statusText" />
      </div>
      <div class="todo-source">
        <el-icon><Share /></el-icon>
        <span>{{ data.source }}</span>
      </div>
    </div>
    <div class="todo-status">
      <CountdownBadge
        v-if="data.status === 'pending' && data.deadline !== undefined"
        :seconds="data.deadline"
      />
      <div v-else-if="data.submittedAt" class="submitted-time">
        <el-icon><Clock /></el-icon>
        <span>{{ data.submittedAt }}</span>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.todo-item {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid transparent;

  &:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
  }

  &.active {
    border-color: #409eff;
    background: #f0f9ff;
  }
}

.todo-main {
  flex: 1;
}

.todo-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  gap: 12px;
}

.todo-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.todo-source {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #909399;
}

.todo-status {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.submitted-time {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #909399;
}
</style>