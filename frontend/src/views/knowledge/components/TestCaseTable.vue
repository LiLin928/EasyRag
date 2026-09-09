<script setup lang="ts">
import { ref, computed } from 'vue'
import type { RetrievalTestCase, TestCaseStatus } from '@/types/knowledge'
import { useKnowledgeStore } from '@/stores/knowledge'
import StatusChip from '@/components/common/StatusChip.vue'
import ConfirmDelete from '@/components/common/ConfirmDelete.vue'
import TestCaseDialog from './TestCaseDialog.vue'

const props = defineProps<{
  setId: string
  kbId: string
  runMode?: boolean
}>()

const knowledgeStore = useKnowledgeStore()

const keyword = ref('')
const tagFilter = ref('')
const statusFilter = ref('all')
const selectedIds = ref<string[]>([])
const dialogOpen = ref(false)
const editCase = ref<RetrievalTestCase | null>(null)

const statusOptions = computed(() =>
  props.runMode
    ? [
        { label: '全部', value: 'all' },
        { label: '命中', value: 'hit' },
        { label: '部分命中', value: 'partial_hit' },
        { label: '未命中', value: 'miss' },
        { label: '失败', value: 'failed' },
        { label: '跳过', value: 'skipped' }
      ]
    : [
        { label: '全部', value: 'all' },
        { label: '启用', value: 'enabled' },
        { label: '禁用', value: 'disabled' }
      ]
)

const filtered = computed(() => {
  let list = props.runMode ? knowledgeStore.runResults : knowledgeStore.testCases
  if (keyword.value) {
    list = list.filter(c => c.query.includes(keyword.value))
  }
  if (tagFilter.value) {
    list = list.filter(c => c.tags.includes(tagFilter.value))
  }
  if (props.runMode) {
    if (statusFilter.value !== 'all') {
      list = list.filter(c => c.status === statusFilter.value)
    }
  } else {
    if (statusFilter.value === 'enabled') list = list.filter(c => c.enabled)
    if (statusFilter.value === 'disabled') list = list.filter(c => !c.enabled)
  }
  return list
})

const allTags = computed(() => {
  const tags = new Set<string>()
  const source = props.runMode ? knowledgeStore.runResults : knowledgeStore.testCases
  source.forEach(c => c.tags.forEach(t => tags.add(t)))
  return Array.from(tags)
})

const statusMap: Record<string, { type: 'ok' | 'err' | 'warn' | 'run' | 'wait' | 'gray'; label: string }> = {
  pending: { type: 'wait', label: '等待' },
  running: { type: 'run', label: '运行中' },
  hit: { type: 'ok', label: '命中' },
  partial_hit: { type: 'warn', label: '部分命中' },
  miss: { type: 'err', label: '未命中' },
  failed: { type: 'err', label: '失败' },
  skipped: { type: 'gray', label: '跳过' }
}

function getStatusInfo(status?: TestCaseStatus) {
  if (!status) return { type: 'gray' as const, label: '-' }
  return statusMap[status] || { type: 'gray' as const, label: status }
}

function expectedLabel(ids: string[]): string {
  return ids.length ? ids.length + ' 篇' : '未标注'
}

function handleEdit(c: RetrievalTestCase) {
  editCase.value = c
  dialogOpen.value = true
}

function handleAdd() {
  editCase.value = null
  dialogOpen.value = true
}

async function handleDelete(caseId: string) {
  await knowledgeStore.removeTestCase(caseId)
}

async function batchSetEnabled(enabled: boolean) {
  if (!selectedIds.value.length) return
  await knowledgeStore.setTestCaseEnabled(selectedIds.value, enabled)
  selectedIds.value = []
}

function selectionChanged(rows: RetrievalTestCase[]) {
  selectedIds.value = rows.map(r => r.id)
}

const emit = defineEmits<{
  'run-selected': [ids: string[]]
  'run-all': []
  'view-case': [c: RetrievalTestCase]
}>()
</script>

<template>
  <div class="test-case-table">
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索查询" clearable size="small" style="width: 180px" />
      <el-select v-model="tagFilter" placeholder="标签" clearable size="small" style="width: 120px">
        <el-option v-for="tag in allTags" :key="tag" :label="tag" :value="tag" />
      </el-select>
      <el-select v-model="statusFilter" size="small" style="width: 120px">
        <el-option v-for="opt in statusOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>

      <div class="toolbar-spacer" />

      <template v-if="!runMode">
        <el-button size="small" icon="Plus" @click="handleAdd">新建用例</el-button>
        <el-button size="small" :disabled="!selectedIds.length" @click="batchSetEnabled(true)">批量启用</el-button>
        <el-button size="small" :disabled="!selectedIds.length" @click="batchSetEnabled(false)">批量禁用</el-button>
        <el-button size="small" type="primary" :disabled="!selectedIds.length" @click="emit('run-selected', selectedIds)">
          运行选中
        </el-button>
        <el-button size="small" type="primary" @click="emit('run-all')">运行全部</el-button>
      </template>
    </div>

    <el-table
      :data="filtered"
      stripe
      size="small"
      @selection-change="selectionChanged"
    >
      <el-table-column v-if="!runMode" type="selection" width="40" />
      <el-table-column label="查询" min-width="200" prop="query" show-overflow-tooltip />

      <el-table-column label="期望文档" width="100">
        <template #default="{ row }">
          <span :class="{ 'expected-unset': !row.expected_doc_ids.length }">
            {{ expectedLabel(row.expected_doc_ids) }}
          </span>
        </template>
      </el-table-column>

      <el-table-column label="标签" width="120">
        <template #default="{ row }">
          <el-tag v-for="tag in row.tags" :key="tag" size="small" style="margin: 1px">{{ tag }}</el-tag>
        </template>
      </el-table-column>

      <el-table-column v-if="runMode" label="状态" width="100">
        <template #default="{ row }">
          <StatusChip :type="getStatusInfo(row.status).type" :label="getStatusInfo(row.status).label" dot />
        </template>
      </el-table-column>

      <el-table-column v-if="runMode" label="首个命中排名" width="110" align="center">
        <template #default="{ row }">
          {{ row.first_expected_hit_rank ?? '-' }}
        </template>
      </el-table-column>

      <el-table-column v-if="runMode" label="耗时" width="80" align="center">
        <template #default="{ row }">
          {{ row.latency_ms != null ? row.latency_ms + 'ms' : '-' }}
        </template>
      </el-table-column>

      <el-table-column v-if="!runMode" label="启用" width="60" align="center">
        <template #default="{ row }">
          <el-switch
            :model-value="row.enabled"
            size="small"
            @change="(val: string | number | boolean) => knowledgeStore.setTestCaseEnabled([row.id], !!val)"
          />
        </template>
      </el-table-column>

      <el-table-column v-if="runMode" label="操作" width="60" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 'failed'"
            link
            type="danger"
            size="small"
            icon="Warning"
            @click="emit('view-case', row as RetrievalTestCase)"
          />
          <el-button
            v-else
            link
            type="primary"
            size="small"
            @click="emit('view-case', row as RetrievalTestCase)"
          >
            明细
          </el-button>
        </template>
      </el-table-column>

      <el-table-column v-if="!runMode" label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="handleEdit(row as RetrievalTestCase)">编辑</el-button>
          <ConfirmDelete @confirm="handleDelete((row as RetrievalTestCase).id)" />
        </template>
      </el-table-column>
    </el-table>

    <TestCaseDialog
      v-if="dialogOpen"
      v-model="dialogOpen"
      :set-id="setId"
      :edit-case="editCase"
      @saved="knowledgeStore.loadTestCases(setId)"
    />
  </div>
</template>

<style lang="scss" scoped>
.test-case-table {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.toolbar-spacer {
  flex: 1;
}

.expected-unset {
  color: #909399;
  font-style: italic;
}
</style>
