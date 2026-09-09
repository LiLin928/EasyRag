<script setup lang="ts">
import { ref } from 'vue'
import type { RetrievalTestSet } from '@/types/knowledge'
import { useKnowledgeStore } from '@/stores/knowledge'
import StatusChip from '@/components/common/StatusChip.vue'
import ConfirmDelete from '@/components/common/ConfirmDelete.vue'

const props = defineProps<{
  kbId: string
}>()

const emit = defineEmits<{
  'select': [set: RetrievalTestSet]
}>()

const knowledgeStore = useKnowledgeStore()
const includeArchived = ref(false)
const showCreateDialog = ref(false)
const newSetName = ref('')
const newSetDesc = ref('')
const creating = ref(false)

function thirdMetricLabel(m: Record<string, Record<string, number | null>> | null | undefined): string {
  if (m && typeof (m as Record<string, unknown>)['mrr'] === 'number') return 'MRR'
  return 'Hit@1'
}

function thirdMetricValue(m: Record<string, Record<string, number | null>> | null | undefined): string {
  if (m && typeof (m as Record<string, unknown>)['mrr'] === 'number') {
    return ((m as Record<string, unknown>)['mrr'] as number * 100).toFixed(0) + '%'
  }
  return fmtHit(m?.hit_at_k, '1')
}

function fmtHit(m: Record<string, number | null> | null | undefined, k: string): string {
  if (!m || m[k] == null) return '-'
  return (m[k]! * 100).toFixed(0) + '%'
}

function fmtTime(v: string | null): string {
  if (!v) return '-'
  return v.replace('T', ' ').slice(0, 16)
}

async function handleCreate() {
  if (!newSetName.value.trim()) return
  creating.value = true
  try {
    await knowledgeStore.saveTestSet(props.kbId, {
      name: newSetName.value.trim(),
      description: newSetDesc.value.trim() || null
    })
    showCreateDialog.value = false
    newSetName.value = ''
    newSetDesc.value = ''
  } finally {
    creating.value = false
  }
}

async function handleArchive(set: RetrievalTestSet) {
  await knowledgeStore.saveTestSet(props.kbId, { archived: !set.archived }, set.id)
}

async function handleDelete(set: RetrievalTestSet) {
  await knowledgeStore.removeTestSet(set.id)
}
</script>

<template>
  <div class="test-set-list">
    <div class="list-header">
      <el-button type="primary" size="small" icon="Plus" @click="showCreateDialog = true">新建集</el-button>
      <el-switch v-model="includeArchived" active-text="包含归档" size="small" style="margin-left: 8px" />
    </div>

    <div class="set-cards">
      <div
        v-for="set in knowledgeStore.testSets.filter(s => includeArchived || !s.archived)"
        :key="set.id"
        class="set-card"
        :class="{ active: knowledgeStore.currentTestSet?.id === set.id }"
        @click="emit('select', set)"
      >
        <div class="card-top">
          <span class="set-name">{{ set.name }}</span>
          <StatusChip
            :type="set.archived ? 'gray' : 'ok'"
            :label="set.archived ? '已归档' : '活跃'"
            dot
          />
        </div>
        <div class="card-metrics">
          <span class="metric">
            <span class="metric-label">用例</span>
            <span class="metric-val">{{ set.case_count }}</span>
          </span>
          <span class="metric">
            <span class="metric-label">Hit@3</span>
            <span class="metric-val">{{ fmtHit(set.last_metrics?.hit_at_k, '3') }}</span>
          </span>
          <span class="metric">
            <span class="metric-label">{{ thirdMetricLabel(set.last_metrics) }}</span>
            <span class="metric-val">{{ thirdMetricValue(set.last_metrics) }}</span>
          </span>
        </div>
        <div class="card-meta">
          <span class="meta-time">{{ fmtTime(set.last_run_at) }}</span>
        </div>
        <div class="card-actions" @click.stop>
          <el-button link size="small" @click="handleArchive(set)">
            {{ set.archived ? '恢复' : '归档' }}
          </el-button>
          <ConfirmDelete @confirm="handleDelete(set)" />
        </div>
      </div>

      <el-empty v-if="knowledgeStore.testSets.length === 0" description="暂无测试集" :image-size="60" />
    </div>

    <el-dialog v-model="showCreateDialog" title="新建测试集" width="400px" :append-to-body="true" destroy-on-close>
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="newSetName" placeholder="测试集名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newSetDesc" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" :disabled="!newSetName.trim()" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.test-set-list {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  margin-bottom: 12px;
}

.set-cards {
  flex: 1;
  overflow-y: auto;
}

.set-card {
  padding: 12px;
  border-radius: 6px;
  border: 1px solid var(--el-border-color-lighter);
  margin-bottom: 8px;
  cursor: pointer;
  transition: border-color 0.2s;

  &:hover {
    border-color: var(--el-color-primary-light-5);
  }

  &.active {
    border-color: var(--el-color-primary);
    background: var(--el-color-primary-light-9);
  }
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;

  .set-name {
    font-weight: 600;
    font-size: 14px;
    color: #303133;
  }
}

.card-metrics {
  display: flex;
  gap: 16px;
  margin-bottom: 6px;
}

.metric {
  display: flex;
  flex-direction: column;
  align-items: center;

  .metric-label {
    font-size: 11px;
    color: #909399;
  }
  .metric-val {
    font-size: 14px;
    font-weight: 600;
    color: #303133;
  }
}

.card-meta {
  .meta-time {
    font-size: 12px;
    color: #909399;
  }
}

.card-actions {
  display: flex;
  gap: 4px;
  margin-top: 6px;
}
</style>
