<script setup lang="ts">
import { computed } from 'vue'
import StatusChip from '@/components/common/StatusChip.vue'
import ConfirmDelete from '@/components/common/ConfirmDelete.vue'
import type { Tool } from '@/types/tool'

interface Props {
  data: Tool
}

const props = defineProps<Props>()

const emit = defineEmits<{
  config: [tool: Tool]
  test: [tool: Tool]
  delete: [id: string]
  toggle: [id: string, enabled: boolean]
}>()

// 映射工具类型到状态徽标
const typeStatusMap = {
  'HTTP': 'run',
  '内置': 'gray',
  'Python': 'wait'
} as const

const typeStatus = computed(() => typeStatusMap[props.data.type] || 'gray')

function handleConfig() {
  emit('config', props.data)
}

function handleTest() {
  emit('test', props.data)
}

function handleToggle(val: string | number | boolean) {
  const enabled = Boolean(val)
  emit('toggle', props.data.id, enabled)
}

function handleDelete() {
  emit('delete', props.data.id)
}
</script>

<template>
  <div class="tool-card">
    <div class="tool-header">
      <div class="tool-type">
        <StatusChip :type="typeStatus" :label="data.type" />
      </div>
      <el-switch
        :model-value="data.enabled"
        @update:model-value="handleToggle"
        size="small"
      />
    </div>

    <div class="tool-content">
      <h3 class="tool-name">{{ data.name }}</h3>
      <p class="tool-desc">{{ data.desc }}</p>

      <div class="tool-sig">
        <code>{{ data.sig }}</code>
      </div>

      <div class="tool-meta">
        <span class="meta-item">
          <el-icon><Operation /></el-icon>
          {{ data.params.length }} 个参数
        </span>
        <span class="meta-item">
          <el-icon><Lock /></el-icon>
          {{ data.auth.mode === 'none' ? '无鉴权' : data.auth.mode }}
        </span>
      </div>
    </div>

    <div class="tool-actions">
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
.tool-card {
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

.tool-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tool-content {
  flex: 1;
}

.tool-name {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.tool-desc {
  margin: 0 0 12px;
  font-size: 13px;
  color: #909399;
  line-height: 1.5;
  min-height: 40px;
}

.tool-sig {
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

.tool-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #909399;

  .meta-item {
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

.tool-actions {
  display: flex;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
}
</style>
