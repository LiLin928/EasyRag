<script setup lang="ts">
import { computed } from 'vue'
import StatusChip from '@/components/common/StatusChip.vue'
import ConfirmDelete from '@/components/common/ConfirmDelete.vue'
import type { Skill } from '@/types/skill'

interface Props {
  data: Skill
}

const props = defineProps<Props>()

const emit = defineEmits<{
  config: [skill: Skill]
  duplicate: [id: string]
  delete: [id: string]
}>()

// 映射范围到状态徽标
const scopeStatusMap = {
  'builtin': 'gray',
  'custom': 'run'
} as const

const scopeStatus = computed(() => scopeStatusMap[props.data.scope])

const scopeLabelMap = {
  'builtin': '内置',
  'custom': '自定义'
} as const

const scopeLabel = computed(() => scopeLabelMap[props.data.scope])

function handleConfig() {
  emit('config', props.data)
}

function handleDuplicate() {
  emit('duplicate', props.data.id)
}

function handleDelete() {
  emit('delete', props.data.id)
}
</script>

<template>
  <div class="skill-card">
    <div class="skill-header">
      <div class="skill-icon">{{ data.ico }}</div>
      <div class="skill-scope">
        <StatusChip :type="scopeStatus" :label="scopeLabel" />
      </div>
    </div>

    <div class="skill-content">
      <h3 class="skill-name">{{ data.name }}</h3>
      <p class="skill-desc">{{ data.desc }}</p>

      <div class="skill-meta">
        <span class="meta-item">
          <el-icon><Document /></el-icon>
          版本 {{ data.ver }}
        </span>
        <span class="meta-item">
          <el-icon><ChatDotRound /></el-icon>
          {{ data.examples.length }} 个示例
        </span>
        <span class="meta-item">
          <el-icon><Link /></el-icon>
          {{ data.tools.length + data.docs.length + data.wfs.length }} 个挂载
        </span>
      </div>
    </div>

    <div class="skill-actions">
      <el-button size="small" icon="Setting" @click="handleConfig">
        配置
      </el-button>
      <el-button size="small" icon="CopyDocument" @click="handleDuplicate">
        复制
      </el-button>
      <ConfirmDelete
        v-if="data.scope === 'custom'"
        @confirm="handleDelete"
      />
      <el-button
        v-else
        size="small"
        icon="Delete"
        disabled
        title="内置技能不可删除"
      >
        删除
      </el-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.skill-card {
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

.skill-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.skill-icon {
  font-size: 32px;
  line-height: 1;
}

.skill-content {
  flex: 1;
}

.skill-name {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.skill-desc {
  margin: 0 0 12px;
  font-size: 13px;
  color: #909399;
  line-height: 1.5;
  min-height: 40px;
}

.skill-meta {
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

.skill-actions {
  display: flex;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
}
</style>
