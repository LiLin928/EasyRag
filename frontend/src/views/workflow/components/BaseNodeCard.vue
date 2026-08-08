<script setup lang="ts">
import { computed } from 'vue'
import type { NodeProps } from '@vue-flow/core'
import type { NodeType } from '@/types/workflow'

const props = defineProps<{
  node: NodeProps
  selected?: boolean
  execStatus?: 'idle' | 'running' | 'success' | 'error' | 'wait'
  execDuration?: number
}>()

const nodeConfig: Record<NodeType, { color: string; bgColor: string; icon: string }> = {
  start: { color: '#334155', bgColor: '#f1f5f9', icon: 'VideoPlay' },
  end: { color: '#334155', bgColor: '#f1f5f9', icon: 'VideoPause' },
  condition: { color: '#CA8A04', bgColor: '#fefce8', icon: 'Share' },
  loop: { color: '#0891B2', bgColor: '#ecfeff', icon: 'Refresh' },
  human: { color: '#7C3AED', bgColor: '#faf5ff', icon: 'User' },
  variable_assign: { color: '#64748B', bgColor: '#f8fafc', icon: 'Edit' },
  template_render: { color: '#B45309', bgColor: '#fffbeb', icon: 'Document' },
  llm: { color: '#0369A1', bgColor: '#eff6ff', icon: 'ChatDotSquare' },
  rag: { color: '#0D9488', bgColor: '#f0fdfa', icon: 'Search' },
  code: { color: '#BE123C', bgColor: '#fff1f2', icon: 'Cpu' },
  http: { color: '#C2410C', bgColor: '#fff7ed', icon: 'Link' },
  tool: { color: '#9D174D', bgColor: '#fdf4ff', icon: 'Setting' }
}

const config = computed(() => {
  return nodeConfig[props.node.type as NodeType] || nodeConfig.start
})

const execBorderColor = computed(() => {
  if (!props.execStatus || props.execStatus === 'idle') return undefined
  const colors: Record<string, string> = {
    running: '#0284C7',
    success: '#16A34A',
    error: '#DC2626',
    wait: '#7C3AED'
  }
  return colors[props.execStatus]
})

const statusLabel = computed(() => {
  if (!props.execStatus || props.execStatus === 'idle') return ''
  const labels: Record<string, string> = {
    running: '运行中',
    success: '成功',
    error: '失败',
    wait: '等待'
  }
  return labels[props.execStatus]
})

function formatDuration(ms?: number) {
  if (!ms) return ''
  if (ms < 1000) return ms + 'ms'
  return (ms / 1000).toFixed(1) + 's'
}
</script>

<template>
  <div 
    class="base-node-card"
    :class="{ selected, [execStatus || '']: true }"
    :style="{
      borderColor: execBorderColor || config.color,
      backgroundColor: config.bgColor
    }"
  >
    <div class="node-header">
      <el-icon :style="{ color: config.color }" :size="18">
        <component :is="config.icon" />
      </el-icon>
      <span class="node-name">{{ node.data?.name || node.type }}</span>
      <el-tag v-if="execStatus && execStatus !== 'idle'" :type="execStatus === 'success' ? 'success' : execStatus === 'error' ? 'danger' : execStatus === 'running' ? 'primary' : 'warning'" size="small">
        {{ statusLabel }}
      </el-tag>
    </div>
    
    <div v-if="node.data?.rows?.length" class="node-rows">
      <div v-for="(row, i) in node.data.rows" :key="i" class="node-row">
        <span class="row-key">{{ row[0] }}</span>
        <span class="row-value">{{ row[1] }}</span>
      </div>
    </div>
    
    <div v-if="execDuration" class="node-duration">
      {{ formatDuration(execDuration) }}
    </div>
    
    <div class="handle input" />
    <div class="handle output" />
    
    <template v-if="node.type === 'condition'">
      <div class="handle output-left" />
      <div class="handle output-right" />
    </template>
  </div>
</template>

<style lang="scss" scoped>
.base-node-card {
  position: relative;
  min-width: 180px;
  padding: 12px 16px;
  border-radius: 8px;
  border-width: 2px;
  border-style: solid;
  cursor: pointer;
  transition: all 0.2s;
  
  &.selected {
    box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.5);
  }
  
  &.running {
    animation: pulse 1.5s infinite;
  }
  
  &:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  
  .node-name {
    flex: 1;
    font-size: 14px;
    font-weight: 500;
    color: #303133;
  }
}

.node-rows {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.node-row {
  display: flex;
  gap: 8px;
  font-size: 12px;
  
  .row-key {
    color: #909399;
    min-width: 50px;
  }
  
  .row-value {
    color: #606266;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.node-duration {
  position: absolute;
  top: -20px;
  right: 0;
  font-size: 11px;
  color: #909399;
  background: #fff;
  padding: 2px 6px;
  border-radius: 4px;
}

.handle {
  position: absolute;
  width: 12px;
  height: 12px;
  background: #fff;
  border: 2px solid #409eff;
  border-radius: 50%;
  
  &.input {
    left: -6px;
    top: 50%;
    transform: translateY(-50%);
  }
  
  &.output {
    right: -6px;
    top: 50%;
    transform: translateY(-50%);
  }
  
  &.output-left {
    right: -6px;
    top: 30%;
  }
  
  &.output-right {
    right: -6px;
    top: 70%;
  }
}
</style>
