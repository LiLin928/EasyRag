<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position, type NodeProps } from '@vue-flow/core'
import type { NodeType } from '@/types/workflow'
import { useWorkflowEditorStore } from '@/stores/workflow'

const props = defineProps<{
  node: NodeProps
  selected?: boolean
  execStatus?: 'idle' | 'running' | 'success' | 'error' | 'wait'
  execDuration?: number
}>()

const editorStore = useWorkflowEditorStore()

const nodeConfig: Record<NodeType, { color: string; bgColor: string; icon: string }> = {
  start: { color: '#334155', bgColor: '#f1f5f9', icon: 'VideoPlay' },
  end: { color: '#334155', bgColor: '#f1f5f9', icon: 'VideoPause' },
  condition: { color: '#CA8A04', bgColor: '#fefce8', icon: 'Share' },
  loop: { color: '#0891B2', bgColor: '#ecfeff', icon: 'Refresh' },
  loop_end: { color: '#0891B2', bgColor: '#ecfeff', icon: 'CircleCheck' },
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

// 点击设置图标打开节点配置抽屉
function openConfig() {
  editorStore.selectedNodeId = props.node.id
}

// Vue Flow Handle 连接点样式（统一主色描边）
const handleStyle = {
  background: '#fff',
  border: '2px solid #409eff',
  width: '10px',
  height: '10px'
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
    <!-- 右上角设置图标 -->
    <div class="node-settings-btn" @click.stop="openConfig" @mousedown.stop>
      <el-icon :size="14"><Setting /></el-icon>
    </div>

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

    <!-- 输入连接点（左侧）：开始节点无输入 -->
    <Handle
      v-if="node.type !== 'start'"
      type="target"
      :position="Position.Left"
      :style="handleStyle"
    />

    <!-- 输出连接点（右侧）：条件分支两个输出，结束节点无输出 -->
    <template v-if="node.type === 'condition'">
      <Handle id="yes" type="source" :position="Position.Right" :style="{ ...handleStyle, top: '30%' }" />
      <Handle id="no" type="source" :position="Position.Right" :style="{ ...handleStyle, top: '70%' }" />
    </template>
    <Handle
      v-else-if="node.type !== 'end'"
      type="source"
      :position="Position.Right"
      :style="handleStyle"
    />
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

  &:hover .node-settings-btn {
    opacity: 1;
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.node-settings-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s, background 0.15s;
  color: #909399;
  z-index: 5;

  &:hover {
    background: rgba(0, 0, 0, 0.08);
    color: #409eff;
  }
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
</style>