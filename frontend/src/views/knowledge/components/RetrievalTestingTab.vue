<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount, onMounted } from 'vue'
import type { RetrievalTestSet, RetrievalTestCase, RetrievalTestCaseResult, RetrievalCandidate } from '@/types/knowledge'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useRoute } from 'vue-router'
import TestSetList from './TestSetList.vue'
import TestCaseTable from './TestCaseTable.vue'
import TestRunPanel from './TestRunPanel.vue'
import CandidateDetailDrawer from './CandidateDetailDrawer.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const props = defineProps<{
  kbId: string
}>()

const knowledgeStore = useKnowledgeStore()
const route = useRoute()

const rightTab = ref<'cases' | 'candidates' | 'config'>('cases')
const selectedResultCase = ref<RetrievalTestCase | null>(null)
const drawerOpen = ref(false)
const drawerCandidate = ref<RetrievalCandidate | null>(null)
const testRunPanelRef = ref<InstanceType<typeof TestRunPanel> | null>(null)

const hasActiveRun = computed(() => {
  const run = knowledgeStore.currentRun
  return run?.status === 'running' || run?.status === 'pending'
})

const currentRun = computed(() => knowledgeStore.currentRun)

const activeResult = computed<RetrievalTestCaseResult | null>(() => {
  if (!selectedResultCase.value) return null
  return knowledgeStore.runResults.find(r => r.id === selectedResultCase.value!.id) || null
})

const candidates = computed<RetrievalCandidate[]>(() => {
  if (!activeResult.value) return []
  return activeResult.value.results || []
})

// Load test sets on mount
onMounted(async () => {
  await knowledgeStore.loadTestSets(props.kbId)
})

// Stop polling on KB switch or unmount
watch(() => props.kbId, (newId, oldId) => {
  if (newId !== oldId) {
    knowledgeStore.selectTestSet(null)
  }
})

// Stop polling on route leave
watch(() => route.params.kbId, () => {
  knowledgeStore.stopRunPolling()
})

onBeforeUnmount(() => {
  knowledgeStore.stopRunPolling()
})

async function selectSet(set: RetrievalTestSet) {
  knowledgeStore.selectTestSet(set)
  await Promise.all([
    knowledgeStore.loadTestCases(set.id),
    knowledgeStore.loadDocuments(props.kbId, 1, 100)
  ])
  // Epoch guard: bail if user switched test set while we awaited
  if (knowledgeStore.currentTestSet?.id !== set.id) return
  // Check for active runs
  const runs = await knowledgeStore.loadTestRuns(set.id)
  if (knowledgeStore.currentTestSet?.id !== set.id) return
  const active = runs.find(r => r.status === 'running' || r.status === 'pending')
  if (active) {
    knowledgeStore.clearRunState()
    knowledgeStore.setCurrentRun(active)
    void knowledgeStore.pollTestRun(active.id)
  } else {
    knowledgeStore.setCurrentRun(runs[0] || null)
    if (runs.length) {
      void knowledgeStore.loadRunResults(runs[0].id)
    }
  }
  rightTab.value = 'cases'
}

function handleViewCase(c: RetrievalTestCase) {
  selectedResultCase.value = c
  rightTab.value = 'candidates'
}

function handleCandidateClick(candidate: RetrievalCandidate) {
  drawerCandidate.value = candidate
  drawerOpen.value = true
}

async function handleRunStarted() {
  rightTab.value = 'cases'
}

async function handleRunSelected(caseIds: string[]) {
  const ks = testRunPanelRef.value?.selectedKs ?? []
  if (!ks.length) return
  const payload = { case_ids: caseIds, ks }
  await knowledgeStore.startTestRun(knowledgeStore.currentTestSet!.id, payload)
  rightTab.value = 'cases'
}

async function handleRunAll() {
  const ks = testRunPanelRef.value?.selectedKs ?? []
  if (!ks.length) return
  const enabledCases = knowledgeStore.testCases.filter(c => c.enabled)
  const payload = { case_ids: enabledCases.map(c => c.id), ks }
  await knowledgeStore.startTestRun(knowledgeStore.currentTestSet!.id, payload)
  rightTab.value = 'cases'
}

function fmtScore(v: number | null): string {
  return v != null ? v.toFixed(4) : '-'
}

const sourceTagMap: Record<string, string> = {
  override: '测试覆盖',
  knowledge_base: '知识库',
  scene: '场景',
  system_default: '系统默认'
}

interface ConfigSourceVal {
  value: unknown
  source: string
}

function getConfigValue(val: unknown): ConfigSourceVal {
  if (val && typeof val === 'object' && 'value' in val && 'source' in val) {
    return val as ConfigSourceVal
  }
  return { value: val, source: 'system_default' }
}

const configSnapshot = computed(() => currentRun.value?.config_snapshot)
</script>

<template>
  <div class="retrieval-testing-tab">
    <div class="left-panel">
      <TestSetList :kb-id="kbId" @select="selectSet" />
    </div>

    <div v-if="knowledgeStore.currentTestSet" class="right-panel">
      <!-- Run panel -->
      <div class="run-panel-wrapper">
        <TestRunPanel
          ref="testRunPanelRef"
          :set-id="knowledgeStore.currentTestSet.id"
          :kb-id="kbId"
          :disabled="hasActiveRun"
          @run-started="handleRunStarted"
        />
      </div>

      <!-- Right inner tabs -->
      <el-tabs v-model="rightTab" class="result-tabs">
        <el-tab-pane label="用例结果" name="cases">
          <TestCaseTable
            :set-id="knowledgeStore.currentTestSet.id"
            :kb-id="kbId"
            :run-mode="!!currentRun"
            @run-selected="handleRunSelected"
            @run-all="handleRunAll"
            @view-case="handleViewCase"
          />
        </el-tab-pane>

        <el-tab-pane label="命中明细" name="candidates" :disabled="!selectedResultCase">
          <el-table v-if="candidates.length" :data="candidates" stripe size="small">
            <el-table-column label="Rank" prop="rank" width="60" align="center" />
            <el-table-column label="文档" prop="document_name" min-width="140" show-overflow-tooltip />
            <el-table-column label="章节" prop="section_path" width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.section_path || '-' }}</template>
            </el-table-column>
            <el-table-column label="页码" prop="page_number" width="60" align="center" />
            <el-table-column label="向量分" width="80" align="center">
              <template #default="{ row }">{{ fmtScore(row.vector_score) }}</template>
            </el-table-column>
            <el-table-column label="关键词分" width="80" align="center">
              <template #default="{ row }">{{ fmtScore(row.keyword_score) }}</template>
            </el-table-column>
            <el-table-column label="RRF" width="80" align="center">
              <template #default="{ row }">{{ fmtScore(row.rrf_score) }}</template>
            </el-table-column>
            <el-table-column label="Rerank" width="80" align="center">
              <template #default="{ row }">{{ fmtScore(row.rerank_score) }}</template>
            </el-table-column>
            <el-table-column label="命中" width="60" align="center">
              <template #default="{ row }">
                <el-icon v-if="selectedResultCase?.expected_doc_ids.includes(row.document_id)" color="#16A34A"><Select /></el-icon>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="60" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="handleCandidateClick(row as RetrievalCandidate)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="选择一个用例查看候选明细" :image-size="60" />
        </el-tab-pane>

        <el-tab-pane label="生效配置" name="config">
          <template v-if="configSnapshot">
            <el-descriptions :column="2" border size="small" title="模型">
              <el-descriptions-item label="Embedding模型">
                {{ configSnapshot.embedding_model?.name || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="Rerank模型">
                {{ configSnapshot.rerank_model?.name || '-' }}
              </el-descriptions-item>
            </el-descriptions>

            <el-descriptions :column="1" border size="small" title="K值与过滤" style="margin-top: 16px">
              <el-descriptions-item label="K值">
                {{ configSnapshot.ks.join(', ') }}
              </el-descriptions-item>
              <el-descriptions-item label="文档元数据过滤">
                {{ Object.keys(configSnapshot.document_metadata).length ? JSON.stringify(configSnapshot.document_metadata) : '无' }}
              </el-descriptions-item>
              <el-descriptions-item label="分段元数据过滤">
                {{ Object.keys(configSnapshot.chunk_metadata).length ? JSON.stringify(configSnapshot.chunk_metadata) : '无' }}
              </el-descriptions-item>
            </el-descriptions>

            <el-descriptions :column="1" border size="small" title="配置来源" style="margin-top: 16px">
              <el-descriptions-item
                v-for="(val, key) in configSnapshot.settings.values"
                :key="String(key)"
                :label="String(key)"
              >
                {{ getConfigValue(val).value }}
                <el-tag size="small" type="info" style="margin-left: 6px">
                  {{ sourceTagMap[getConfigValue(val).source] || getConfigValue(val).source }}
                </el-tag>
              </el-descriptions-item>
            </el-descriptions>
          </template>
          <el-empty v-else description="运行测试后查看生效配置" :image-size="60" />
        </el-tab-pane>
      </el-tabs>
    </div>

    <div v-else class="right-panel-empty">
      <EmptyState icon="DataAnalysis" text="选择测试集开始" />
    </div>

    <CandidateDetailDrawer
      v-model="drawerOpen"
      :candidate="drawerCandidate"
      :test-case="selectedResultCase"
    />
  </div>
</template>

<style lang="scss" scoped>
.retrieval-testing-tab {
  display: flex;
  gap: 16px;
  height: 100%;
  min-height: 500px;
}

.left-panel {
  width: 280px;
  flex-shrink: 0;
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 16px;
  overflow-y: auto;
}

.right-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.right-panel-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-bg-color);
  border-radius: 8px;
}

.run-panel-wrapper {
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 16px;
}

.result-tabs {
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 16px;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;

  :deep(.el-tabs__content) {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }
}
</style>
