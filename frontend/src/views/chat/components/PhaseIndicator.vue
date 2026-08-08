<script setup lang="ts">
import { computed } from 'vue'
import type { Phase } from '@/types/chat'

interface Props {
  phase: Phase
}

const props = defineProps<Props>()

const phases = [
  { key: 'parse', label: '解析', icon: 'Document' },
  { key: 'navigate', label: '导航', icon: 'Guide' },
  { key: 'retrieve', label: '检索', icon: 'Search' },
  { key: 'generate', label: '生成', icon: 'EditPen' }
]

const phaseIndex = computed(() => {
  return phases.findIndex(p => p.key === props.phase)
})

function getPhaseStatus(index: number): 'done' | 'active' | 'pending' {
  if (phaseIndex.value > index) return 'done'
  if (phaseIndex.value === index) return 'active'
  return 'pending'
}
</script>

<template>
  <div class="phase-indicator">
    <div
      v-for="(phase, index) in phases"
      :key="phase.key"
      class="phase-item"
      :class="getPhaseStatus(index)"
    >
      <div class="phase-icon">
        <el-icon v-if="getPhaseStatus(index) === 'done'"><Check /></el-icon>
        <el-icon v-else-if="getPhaseStatus(index) === 'active'" class="is-loading"><Loading /></el-icon>
        <el-icon v-else><component :is="phase.icon" /></el-icon>
      </div>
      <span class="phase-label">{{ phase.label }}</span>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.phase-indicator {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 12px 16px;
  background: #fff;
  border-radius: 8px;
  margin-bottom: 12px;
}

.phase-item {
  display: flex;
  align-items: center;
  gap: 6px;
  
  .phase-icon {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
  }
  
  .phase-label {
    font-size: 13px;
  }
  
  // 待处理
  &.pending {
    color: #c0c4cc;
    
    .phase-icon {
      background: #f0f0f0;
    }
  }
  
  // 进行中
  &.active {
    color: #409eff;
    
    .phase-icon {
      background: #ecf5ff;
    }
  }
  
  // 已完成
  &.done {
    color: #67c23a;
    
    .phase-icon {
      background: #f0f9eb;
    }
  }
}
</style>
