<script setup lang="ts">
import { ref, computed } from 'vue'
import type { RetrievalTestRun, RetrievalRunPayload } from '@/types/knowledge'
import { useKnowledgeStore } from '@/stores/knowledge'
import StatusChip from '@/components/common/StatusChip.vue'

const props = defineProps<{
  setId: string
  kbId: string
  disabled: boolean
}>()

const emit = defineEmits<{
  'run-started': [run: RetrievalTestRun]
}>()

const knowledgeStore = useKnowledgeStore()

const k3 = ref(true)
const k5 = ref(true)
const k10 = ref(false)
const overrideExpanded = ref<string[]>([])
const overrideMethod = ref('')
const cancelling = ref(false)

const selectedKs = computed(() => {
  const ks: number[] = []
  if (k3.value) ks.push(3)
  if (k5.value) ks.push(5)
  if (k10.value) ks.push(10)
  return ks
})

defineExpose({ selectedKs })

const isRunning = computed(() => {
  const run = knowledgeStore.currentRun
  return run?.status === 'running' || run?.status === 'pending'
})

const progressPct = computed(() => {
  const run = knowledgeStore.currentRun
  if (!run || run.total_cases === 0) return 0
  return Math.round((run.completed_cases / run.total_cases) * 100)
})

const metrics = computed(() => {
  const run = knowledgeStore.currentRun
  if (!run || !run.metrics) return null
  return run.metrics
})

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '-'
  return (v * 100).toFixed(1) + '%'
}

function fmtPercentile(metrics: Record<string, Record<string, number | null> | number | null>): string {
  const p50 = metrics.p50_latency_ms
  if (typeof p50 === 'number') return p50 + 'ms'
  return '-'
}

function fmtP95(metrics: Record<string, Record<string, number | null> | number | null>): string {
  const p95 = metrics.p95_latency_ms
  if (typeof p95 === 'number') return p95 + 'ms'
  return '-'
}

async function handleRun(caseIds?: string[]) {
  const payload: RetrievalRunPayload = {
    ks: selectedKs.value
  }
  if (caseIds?.length) payload.case_ids = caseIds
  if (overrideMethod.value) {
    payload.override_config = { method: overrideMethod.value }
  }
  const run = await knowledgeStore.startTestRun(props.setId, payload)
  emit('run-started', run)
}

async function handleCancel() {
  const run = knowledgeStore.currentRun
  if (!run) return
  cancelling.value = true
  try {
    await knowledgeStore.cancelTestRun(run.id)
    // poll once immediately after cancel
    await knowledgeStore.pollTestRun(run.id)
  } finally {
    cancelling.value = false
  }
}
</script>

<template>
  <div class="test-run-panel">
    <!-- Idle state -->
    <template v-if="!isRunning">
      <div class="config-row">
        <span class="config-label">K值</span>
        <el-checkbox v-model="k3" :disabled="disabled">3</el-checkbox>
        <el-checkbox v-model="k5" :disabled="disabled">5</el-checkbox>
        <el-checkbox v-model="k10" :disabled="disabled">10</el-checkbox>
      </div>

      <el-collapse v-model="overrideExpanded">
        <el-collapse-item title="覆盖配置" name="override">
          <el-form size="small" label-width="80px">
            <el-form-item label="检索方法">
              <el-select v-model="overrideMethod" placeholder="默认" clearable style="width: 160px">
                <el-option label="向量" value="vector" />
                <el-option label="关键词" value="keyword" />
                <el-option label="混合" value="hybrid" />
              </el-select>
            </el-form-item>
          </el-form>
        </el-collapse-item>
      </el-collapse>

      <el-button type="primary" :disabled="disabled || !selectedKs.length" @click="handleRun()">
        运行测试
      </el-button>
    </template>

    <!-- Running state -->
    <template v-else>
      <div class="run-status">
        <StatusChip type="run" label="运行中" dot />
        <el-progress :percentage="progressPct" :stroke-width="8" style="flex: 1" />
        <span class="run-progress-text">
          {{ knowledgeStore.currentRun?.completed_cases || 0 }} / {{ knowledgeStore.currentRun?.total_cases || 0 }}
        </span>
      </div>
      <el-button type="danger" :loading="cancelling" @click="handleCancel">取消</el-button>
    </template>

    <!-- Error banner -->
    <el-alert
      v-if="knowledgeStore.currentRun?.status === 'failed' || knowledgeStore.currentRun?.error"
      type="error"
      :title="knowledgeStore.currentRun?.error || '运行失败'"
      show-icon
      :closable="false"
      style="margin-top: 12px"
    />

    <!-- Metrics cards -->
    <div v-if="metrics && (knowledgeStore.currentRun?.status === 'completed' || knowledgeStore.currentRun?.status === 'canceled')" class="metrics-row">
      <div class="metric-card">
        <span class="metric-title">Hit@K</span>
        <div class="metric-chips">
          <el-tag
            v-for="k in selectedKs"
            :key="k"
            size="small"
            type="success"
            style="margin: 2px"
          >
            @{{ k }}: {{ fmtPct((metrics.hit_at_k as Record<string, number | null>)?.[String(k)]) }}
          </el-tag>
        </div>
      </div>
      <div class="metric-card">
        <span class="metric-title">Recall@K</span>
        <div class="metric-chips">
          <el-tag
            v-for="k in selectedKs"
            :key="k"
            size="small"
            type="warning"
            style="margin: 2px"
          >
            @{{ k }}: {{ fmtPct((metrics.recall_at_k as Record<string, number | null>)?.[String(k)]) }}
          </el-tag>
        </div>
      </div>
      <div class="metric-card">
        <span class="metric-title">MRR</span>
        <span class="metric-value">{{ fmtPct(metrics.mrr as number | null | undefined) }}</span>
      </div>
      <div class="metric-card">
        <span class="metric-title">P50</span>
        <span class="metric-value">{{ fmtPercentile(metrics) }}</span>
      </div>
      <div class="metric-card">
        <span class="metric-title">P95</span>
        <span class="metric-value">{{ fmtP95(metrics) }}</span>
      </div>
      <div class="metric-card">
        <span class="metric-title">Rerank触发率</span>
        <span class="metric-value">{{ fmtPct(metrics.rerank_trigger_rate as number | null | undefined) }}</span>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.test-run-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.config-row {
  display: flex;
  align-items: center;
  gap: 12px;

  .config-label {
    font-size: 14px;
    font-weight: 500;
    color: #303133;
  }
}

.run-status {
  display: flex;
  align-items: center;
  gap: 12px;
}

.run-progress-text {
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
}

.metric-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 4px;
  background: #f9fafb;
  border-radius: 6px;
  height: 72px;
  box-sizing: border-box;

  .metric-title {
    font-size: 12px;
    color: #909399;
    margin-bottom: 4px;
  }

  .metric-value {
    font-size: 18px;
    font-weight: 600;
    color: #303133;
  }
}

.metric-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 2px;
}

@media (max-width: 1024px) {
  .metrics-row {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
