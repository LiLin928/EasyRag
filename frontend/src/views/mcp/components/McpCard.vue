<script setup lang="ts">
import { computed } from 'vue'
import StatusChip from '@/components/common/StatusChip.vue'
import ConfirmDelete from '@/components/common/ConfirmDelete.vue'
import type { Mcp } from '@/types/mcp'

interface Props {
  data: Mcp
}

const props = defineProps<Props>()

const emit = defineEmits<{
  config: [mcp: Mcp]
  test: [mcp: Mcp]
  delete: [id: string]
  toggle: [id: string, status: 'on' | 'off']
}>()

// 映射 MCP 类型到状态徽标
const typeStatusMap = {
  'stdio': 'run',
  'SSE': 'wait'
} as const

const typeStatus = computed(() => typeStatusMap[props.data.tp])

// 映射状态到徽标
const statusMap = {
  'on': 'ok',
  'off': 'gray',
  'err': 'err'
} as const

const statusType = computed(() => statusMap[props.data.status])

const statusLabelMap = {
  'on': '运行中',
  'off': '已停止',
  'err': '错误'
} as const

const statusLabel = computed(() => statusLabelMap[props.data.status])

function handleConfig() {
  emit('config', props.data)
}

function handleTest() {
  emit('test', props.data)
}

function handleToggle(val: string | number | boolean) {
  const status = Boolean(val) ? 'on' : 'off'
  emit('toggle', props.data.id, status)
}

function handleDelete() {
  emit('delete', props.data.id)
}
</script>

<template>
  <div class="mcp-card">
    <div class="mcp-header">
      <div class="mcp-type">
        <StatusChip :type="typeStatus" :label="data.tp" />
      </div>
      <el-switch
        :model-value="data.status === 'on'"
        @update:model-value="handleToggle"
        size="small"
      />
    </div>

    <div class="mcp-content">
      <h3 class="mcp-name">{{ data.name }}</h3>

      <div class="mcp-cmd">
        <code>{{ data.cmd }}</code>
      </div>

      <div class="mcp-meta">
        <span class="meta-item">
          <StatusChip :type="statusType" :label="statusLabel" />
        </span>
        <span class="meta-item">
          <el-icon><Operation /></el-icon>
          {{ data.toolCount }} 个工具
        </span>
        <span class="meta-item">
          <el-icon><Timer /></el-icon>
          {{ data.timeout }}s 超时
        </span>
      </div>
    </div>

    <div class="mcp-actions">
      <el-button size="small" icon="Setting" @click="handleConfig">
        配置
      </el-button>
      <el-button size="small" icon="Connection" @click="handleTest">
        测试
      </el-button>
      <ConfirmDelete @confirm="handleDelete" />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.mcp-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: all 0.3s;
  display: flex;
  flex-direction: column;
  gap: 12px;

  &:hover {
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  }
}

.mcp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mcp-content {
  flex: 1;
}

.mcp-name {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.mcp-cmd {
  background: #f5f7fa;
  padding: 8px 12px;
  border-radius: 4px;
  margin-bottom: 12px;

  code {
    font-family: 'Courier New', monospace;
    font-size: 12px;
    color: #409eff;
    word-break: break-all;
  }
}

.mcp-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: #909399;

  .meta-item {
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

.mcp-actions {
  display: flex;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
}
</style>
