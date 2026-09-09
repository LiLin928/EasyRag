<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useKnowledgeStore } from '@/stores/knowledge'
import EmptyState from '@/components/common/EmptyState.vue'
import type { RetrievalTestCase } from '@/types/knowledge'

const props = defineProps<{ kbId: string }>()
const knowledgeStore = useKnowledgeStore()

const activeSubTab = ref('immediate')
const testing = ref(false)
const query = ref('')
const runningSetId = ref('')
const selectedSetId = ref('')

const selectedTestSet = computed(() => {
  return knowledgeStore.testSets.find(ts => ts.id === selectedSetId.value) || null
})

onMounted(async () => {
  await Promise.all([
    knowledgeStore.loadHitTestRecords(props.kbId),
    knowledgeStore.loadTestSets(props.kbId)
  ])
  if (knowledgeStore.testSets.length > 0) {
    selectedSetId.value = knowledgeStore.testSets[0].id
    await knowledgeStore.loadTestCases(selectedSetId.value)
  }
})

async function handleHitTest() {
  if (!query.value.trim()) {
    ElMessage.warning('请输入测试问题')
    return
  }
  if (query.value.length > 200) {
    ElMessage.warning('测试问题不能超过200字')
    return
  }
  testing.value = true
  try {
    await knowledgeStore.runHitTest(props.kbId, query.value)
  } catch {
    ElMessage.error('测试失败')
  } finally {
    testing.value = false
  }
}

function formatScore(score: number): string {
  return (score * 100).toFixed(1) + '%'
}

async function handleSelectSet(setId: string) {
  selectedSetId.value = setId
  await knowledgeStore.loadTestCases(setId)
}

async function handleCreateCase() {
  try {
    const { value } = await ElMessageBox.prompt('请输入测试问题', '添加测试用例', {
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    })
    if (!value?.trim()) return
    await knowledgeStore.createTestCase(selectedSetId.value, {
      query: value.trim(),
      expectedDocIds: [],
      expectedChunkIds: [],
      tags: [],
      enabled: true
    })
    ElMessage.success('添加成功')
  } catch {
    // cancelled
  }
}

async function handleDeleteCase(tc: RetrievalTestCase) {
  try {
    await ElMessageBox.confirm('确定要删除此测试用例吗？', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await knowledgeStore.deleteTestCase(tc.id)
    ElMessage.success('删除成功')
  } catch {
    // cancelled
  }
}

async function handleRunTest() {
  if (!selectedSetId.value) return
  runningSetId.value = selectedSetId.value
  try {
    await knowledgeStore.runTestRun(selectedSetId.value, props.kbId)
    ElMessage.success('测试运行完成')
    await knowledgeStore.loadTestSets(props.kbId)
    await knowledgeStore.loadTestCases(selectedSetId.value)
  } catch {
    ElMessage.error('运行失败')
  } finally {
    runningSetId.value = ''
  }
}

const caseStatusType: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
  hit: 'success',
  partial_hit: 'warning',
  miss: 'danger',
  failed: 'info',
  skipped: 'info'
}

const caseStatusLabel: Record<string, string> = {
  hit: '命中',
  partial_hit: '部分命中',
  miss: '未命中',
  failed: '失败',
  skipped: '跳过'
}
</script>

<template>
  <div class="retrieval-test-tab">
    <el-tabs v-model="activeSubTab">
      <el-tab-pane label="即时测试" name="immediate">
        <div class="immediate-section">
          <div class="query-input">
            <el-input
              v-model="query"
              type="textarea"
              :rows="3"
              placeholder="输入测试问题，最多200字"
              maxlength="200"
              show-word-limit
            />
            <el-button type="primary" :loading="testing" @click="handleHitTest" style="margin-top: 12px">
              测试
            </el-button>
          </div>

          <div v-if="knowledgeStore.hitTestResult" class="result-section">
            <h4 class="result-title">召回结果（{{ knowledgeStore.hitTestResult.segments.length }} 条）</h4>
            <div
              v-for="(seg, idx) in knowledgeStore.hitTestResult.segments"
              :key="seg.id"
              class="result-item"
            >
              <div class="result-header">
                <span class="rank-badge">#{{ idx + 1 }}</span>
                <span class="seg-id">{{ seg.id }}</span>
                <span class="doc-name">{{ seg.docName }}</span>
                <span class="char-count">{{ seg.charCount }} 字</span>
                <el-tag size="small" type="success" class="score-tag">
                  分数 {{ formatScore(seg.score) }}
                </el-tag>
              </div>
              <div class="result-content">{{ seg.content }}</div>
              <div v-if="seg.children?.length" class="child-hits">
                <span class="child-title">子段命中 ({{ seg.children.length }})</span>
                <div v-for="child in seg.children" :key="child.id" class="child-item">
                  <span class="child-id">{{ child.id }}</span>
                  <span class="child-score">{{ formatScore(child.score) }}</span>
                  <span class="child-content">{{ child.content }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="history-section">
            <h4 class="result-title">历史记录</h4>
            <EmptyState
              v-if="knowledgeStore.hitTestRecords.length === 0"
              icon="Clock"
              text="暂无测试记录"
            />
            <el-table v-else :data="knowledgeStore.hitTestRecords" border size="small">
              <el-table-column prop="query" label="测试问题" min-width="200" show-overflow-tooltip />
              <el-table-column label="检索模式" width="100">
                <template #default="{ row }">
                  <el-tag size="small">{{ row.retrievalMode }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="createdAt" label="时间" width="160" />
            </el-table>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="批量测试" name="batch">
        <div class="batch-section">
          <div class="batch-layout">
            <div class="set-list">
              <div class="set-list-header">
                <span class="list-title">测试集</span>
                <el-button type="primary" size="small" text @click="handleCreateCase">+ 新建</el-button>
              </div>
              <div
                v-for="ts in knowledgeStore.testSets"
                :key="ts.id"
                class="set-item"
                :class="{ active: ts.id === selectedSetId }"
                @click="handleSelectSet(ts.id)"
              >
                <div class="set-item-name">{{ ts.name }}</div>
                <div class="set-item-meta">
                  {{ ts.caseCount }} 用例
                  <span v-if="ts.lastRunTime"> · {{ ts.lastRunTime }}</span>
                </div>
                <el-tag v-if="ts.status === 'latest'" size="small" type="success">最新</el-tag>
                <el-tag v-else-if="ts.status === 'draft'" size="small" type="info">草稿</el-tag>
              </div>
              <EmptyState v-if="knowledgeStore.testSets.length === 0" icon="Folder" text="暂无测试集" />
            </div>

            <div class="case-detail">
              <template v-if="selectedTestSet">
                <div class="case-header">
                  <div>
                    <h4 class="case-title">{{ selectedTestSet.name }}</h4>
                    <p class="case-desc">{{ selectedTestSet.description }}</p>
                  </div>
                  <el-button
                    type="primary"
                    :loading="runningSetId === selectedSetId"
                    @click="handleRunTest"
                  >
                    运行测试
                  </el-button>
                </div>

                <div v-if="selectedTestSet.lastMetrics" class="metrics-grid">
                  <div class="metric-card">
                    <span class="metric-label">Hit@K</span>
                    <span class="metric-value">{{ (selectedTestSet.lastMetrics.hitAtK * 100).toFixed(1) }}%</span>
                  </div>
                  <div class="metric-card">
                    <span class="metric-label">Recall@K</span>
                    <span class="metric-value">{{ (selectedTestSet.lastMetrics.recallAtK * 100).toFixed(1) }}%</span>
                  </div>
                  <div class="metric-card">
                    <span class="metric-label">MRR</span>
                    <span class="metric-value">{{ selectedTestSet.lastMetrics.mrr.toFixed(3) }}</span>
                  </div>
                  <div class="metric-card">
                    <span class="metric-label">P50 延迟</span>
                    <span class="metric-value">{{ selectedTestSet.lastMetrics.p50Latency }}ms</span>
                  </div>
                  <div class="metric-card">
                    <span class="metric-label">P95 延迟</span>
                    <span class="metric-value">{{ selectedTestSet.lastMetrics.p95Latency }}ms</span>
                  </div>
                  <div class="metric-card">
                    <span class="metric-label">Rerank 触发率</span>
                    <span class="metric-value">{{ (selectedTestSet.lastMetrics.rerankTriggerRate * 100).toFixed(0) }}%</span>
                  </div>
                </div>

                <el-table :data="knowledgeStore.testCases" border size="small" style="margin-top: 16px">
                  <el-table-column prop="query" label="测试问题" min-width="200" show-overflow-tooltip />
                  <el-table-column label="标签" width="120">
                    <template #default="{ row }">
                      <el-tag v-for="tag in row.tags" :key="tag" size="small" class="tag-item">{{ tag }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="上次结果" width="100">
                    <template #default="{ row }">
                      <el-tag v-if="row.lastStatus" size="small" :type="caseStatusType[row.lastStatus]">
                        {{ caseStatusLabel[row.lastStatus] }}
                      </el-tag>
                      <span v-else class="text-muted">-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="命中排名" width="80">
                    <template #default="{ row }">
                      <span v-if="row.lastHitRank">#{{ row.lastHitRank }}</span>
                      <span v-else class="text-muted">-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="延迟" width="80">
                    <template #default="{ row }">
                      <span v-if="row.lastLatency">{{ row.lastLatency }}ms</span>
                      <span v-else class="text-muted">-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="状态" width="60" align="center">
                    <template #default="{ row }">
                      <el-switch v-model="row.enabled" size="small" />
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="60" fixed="right">
                    <template #default="{ row }">
                      <el-button link type="danger" size="small" @click="handleDeleteCase(row as RetrievalTestCase)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </template>
              <EmptyState v-else icon="Folder" text="请选择测试集" />
            </div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style lang="scss" scoped>
.immediate-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.query-input {
  background: #fafafa;
  border-radius: 8px;
  padding: 16px;
}

.result-section .result-title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.result-item {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 8px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}

.seg-id {
  font-size: 12px;
  color: #909399;
  font-family: monospace;
}

.doc-name {
  font-size: 13px;
  color: #606266;
}

.char-count {
  font-size: 12px;
  color: #c0c4cc;
}

.score-tag {
  margin-left: auto;
}

.result-content {
  font-size: 13px;
  color: #303133;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}

.child-hits {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #ebeef5;
}

.child-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
  display: block;
}

.child-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
}

.child-id {
  color: #909399;
  font-family: monospace;
  flex-shrink: 0;
}

.child-score {
  color: #67c23a;
  flex-shrink: 0;
}

.child-content {
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-section .result-title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.batch-layout {
  display: flex;
  gap: 16px;
}

.set-list {
  width: 240px;
  flex-shrink: 0;
}

.set-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.list-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.set-item {
  padding: 10px 12px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  margin-bottom: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.set-item:hover {
  border-color: #409eff;
}

.set-item.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.set-item-name {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}

.set-item-meta {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.case-detail {
  flex: 1;
  min-width: 0;
}

.case-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.case-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.case-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: #909399;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}

.metric-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}

.metric-label {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.metric-value {
  display: block;
  font-size: 18px;
  font-weight: 600;
  color: #409eff;
}

.tag-item {
  margin-right: 4px;
}

.text-muted {
  color: #c0c4cc;
  font-size: 12px;
}
</style>
