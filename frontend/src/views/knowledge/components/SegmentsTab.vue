<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useKnowledgeStore } from '@/stores/knowledge'
import MetadataEditor from './MetadataEditor.vue'
import type { ChunkAsset, MetadataField } from '@/types/knowledge'

interface Props {
  kbId: string
}

const props = defineProps<Props>()
const knowledgeStore = useKnowledgeStore()

type VectorFilter = 'all' | 'vectorized' | 'pending'
type EnabledFilter = 'all' | boolean

const documentKeyword = ref('')
const selectedDocumentId = ref('')
const keyword = ref('')
const vectorFilter = ref<VectorFilter>('all')
const enabledFilter = ref<EnabledFilter>('all')
const metadataFilters = ref<Record<string, unknown>>({})
const page = ref(1)
const pageSize = ref(20)
const selectedIds = ref<string[]>([])
const currentChunk = ref<ChunkAsset | null>(null)
const chunkTableRef = ref()
const drawerVisible = ref(false)
const editorVisible = ref(false)
const editorIds = ref<string[]>([])
const editorMetadata = ref<Record<string, unknown>>({})
const editorMode = ref<'single' | 'batch'>('single')
const metadataSaving = ref(false)
const initialized = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const chunkFields = computed<MetadataField[]>(() =>
  knowledgeStore.metadataFields.filter((field) => field.kb_id === props.kbId && field.scope === 'chunk')
)
const filterableFields = computed<MetadataField[]>(() =>
  chunkFields.value.filter((field) => field.filterable && field.visible)
)
const documents = computed(() =>
  knowledgeStore.docList.filter((item) => !documentKeyword.value || item.name.includes(documentKeyword.value))
)
const selectedChunks = computed<ChunkAsset[]>(() =>
  knowledgeStore.chunkList.filter((item) => selectedIds.value.includes(item.id))
)

watch(keyword, () => {
  if (!initialized.value) return
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    void load()
  }, 300)
})

watch([selectedDocumentId, vectorFilter, enabledFilter], () => {
  if (!initialized.value) return
  page.value = 1
  void load()
})

watch(metadataFilters, () => {
  if (!initialized.value) return
  page.value = 1
  void load()
}, { deep: true })

watch(() => props.kbId, () => {
  selectedDocumentId.value = ''
  keyword.value = ''
  vectorFilter.value = 'all'
  enabledFilter.value = 'all'
  metadataFilters.value = {}
  page.value = 1
  selectedIds.value = []
  currentChunk.value = null
  if (initialized.value) void load()
})

onMounted(() => {
  initialized.value = true
  void load()
})

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
})

async function load(): Promise<void> {
  const filter: Record<string, unknown> = {
    keyword: keyword.value.trim() || undefined,
    page: page.value,
    page_size: pageSize.value
  }
  if (selectedDocumentId.value) filter.document_id = selectedDocumentId.value
  if (vectorFilter.value !== 'all') filter.vector_state = vectorFilter.value
  if (enabledFilter.value !== 'all') filter.enabled = enabledFilter.value
  const metadata = Object.fromEntries(
    Object.entries(metadataFilters.value).filter(([, value]) => hasFilterValue(value))
  )
  if (Object.keys(metadata).length) filter.chunk_metadata = JSON.stringify(metadata)
  await knowledgeStore.loadChunks(props.kbId, filter)
}

function handlePageChange(nextPage: number): void {
  page.value = nextPage
  void load()
}

function handlePageSizeChange(nextSize: number): void {
  pageSize.value = nextSize
  page.value = 1
  void load()
}

function openEditor(chunks: ChunkAsset[]): void {
  editorIds.value = chunks.map((item) => item.id)
  editorMode.value = chunks.length > 1 ? 'batch' : 'single'
  editorMetadata.value = chunks.length === 1 ? { ...chunks[0].metadata } : {}
  editorVisible.value = true
}

async function saveMetadata(metadata: Record<string, unknown>): Promise<void> {
  if (metadataSaving.value) return
  metadataSaving.value = true
  try {
    await knowledgeStore.saveChunkMetadata(props.kbId, editorIds.value, metadata)
    editorVisible.value = false
    if (currentChunk.value && editorIds.value.includes(currentChunk.value.id)) {
      currentChunk.value =
        knowledgeStore.chunkList.find((item) => item.id === currentChunk.value?.id) || currentChunk.value
    }
    ElMessage.success('元数据已更新')
    await load()
  } catch (error) {
    // Keep the dialog open so unsaved values remain editable.
  } finally {
    metadataSaving.value = false
  }
}

async function setEnabled(ids: string[], enabled: boolean): Promise<void> {
  try {
    if (ids.length > 1) {
      await ElMessageBox.confirm(
        `确定要${enabled ? '启用' : '禁用'}选中的 ${ids.length} 个分段吗？`,
        '批量操作确认',
        { confirmButtonText: enabled ? '启用' : '禁用', cancelButtonText: '取消', type: 'warning' }
      )
    }
    await knowledgeStore.setChunkEnabled(props.kbId, ids, enabled)
    if (currentChunk.value && ids.includes(currentChunk.value.id)) {
      currentChunk.value = knowledgeStore.chunkList.find((item) => item.id === currentChunk.value?.id) || currentChunk.value
    }
    selectedIds.value = []
    ElMessage.success('状态已更新')
  } catch (error) {
    // Cancel keeps the current status.
  }
}

async function rebuild(chunkIds: string[]): Promise<void> {
  const chunks = knowledgeStore.chunkList.filter((item) => chunkIds.includes(item.id))
  const documentIds = Array.from(new Set(chunks.map((item) => item.document_id)))
  await knowledgeStore.queueReembedding(props.kbId, documentIds, chunkIds)
  ElMessage.success('向量重建已排队')
}

function openDetail(chunk: ChunkAsset): void {
  currentChunk.value = chunk
  drawerVisible.value = true
}

function hasFilterValue(value: unknown): boolean {
  return value !== undefined && value !== null && value !== '' && (!Array.isArray(value) || value.length > 0)
}

function handleToggle(chunk: ChunkAsset, enabled: boolean): void {
  void setEnabled([chunk.id], enabled)
}

function handleSelection(rows: ChunkAsset[]): void {
  selectedIds.value = rows.map((row) => row.id)
}

watch(selectedIds, (ids) => {
  if (ids.length === 0) chunkTableRef.value?.clearSelection()
})

function formatMetadata(value: unknown): string {
  if (value === null || value === undefined || value === '') return ''
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function metadataLabel(key: string): string {
  return chunkFields.value.find((field) => field.key === key)?.name || key
}

function metadataTags(chunk: ChunkAsset): Array<{ id: string; text: string; missing: boolean }> {
  return chunkFields.value
    .filter((field) => field.visible)
    .map((field) => {
      const value = chunk.metadata[field.key]
      return {
        id: field.id,
        text: formatMetadata(value),
        missing: field.required && value === undefined
      }
    })
    .filter((item) => item.missing || item.text)
}
</script>

<template>
  <section class="segments-tab">
    <aside class="document-panel">
      <div class="panel-title">
        <span>文档</span>
        <el-tag size="small" type="info">{{ documents.length }}</el-tag>
      </div>
      <el-input v-model="documentKeyword" placeholder="搜索文档" clearable prefix-icon="Search" />
      <div class="document-list">
        <button
          type="button"
          class="document-item"
          :class="{ active: selectedDocumentId === '' }"
          @click="selectedDocumentId = ''"
        >
          全部文档
        </button>
        <button
          v-for="item in documents"
          :key="item.id"
          type="button"
          class="document-item"
          :class="{ active: selectedDocumentId === item.id, disabled: !item.enabled }"
          @click="selectedDocumentId = item.id"
        >
          <span class="document-name">{{ item.name }}</span>
          <span class="document-count">{{ item.chunk_count }}</span>
        </button>
      </div>
    </aside>

    <div class="chunk-panel">
      <div class="filter-bar">
        <el-input v-model="keyword" placeholder="搜索分段内容" clearable prefix-icon="Search" class="keyword-input" @clear="load" />
        <el-segmented
          v-model="vectorFilter"
          :options="[
            { label: '全部向量', value: 'all' },
            { label: '已向量化', value: 'vectorized' },
            { label: '未向量化', value: 'pending' }
          ]"
        />
        <el-segmented
          v-model="enabledFilter"
          :options="[
            { label: '全部状态', value: 'all' },
            { label: '启用', value: true },
            { label: '禁用', value: false }
          ]"
        />
      </div>

      <div v-if="filterableFields.length" class="metadata-filter-bar">
        <template v-for="field in filterableFields" :key="field.id">
          <el-select
            v-if="field.data_type === 'select'"
            v-model="metadataFilters[field.key] as string[]"
            multiple
            collapse-tags
            clearable
            filterable
            :placeholder="field.name"
            class="metadata-filter"
          >
            <el-option v-for="option in field.options" :key="option" :label="option" :value="option" />
          </el-select>
          <el-date-picker
            v-else-if="field.data_type === 'date'"
            v-model="metadataFilters[field.key] as string"
            type="date"
            value-format="YYYY-MM-DD"
            :placeholder="field.name"
            class="metadata-filter"
          />
          <el-input-number
            v-else-if="field.data_type === 'number'"
            v-model="metadataFilters[field.key] as number"
            :controls="false"
            :placeholder="field.name"
            class="metadata-filter"
          />
          <el-select
            v-else-if="field.data_type === 'boolean'"
            v-model="metadataFilters[field.key] as boolean"
            clearable
            :placeholder="field.name"
            class="metadata-filter"
          >
            <el-option label="是" :value="true" />
            <el-option label="否" :value="false" />
          </el-select>
          <el-input
            v-else
            v-model="metadataFilters[field.key] as string"
            clearable
            :placeholder="field.name"
            class="metadata-filter"
          />
        </template>
      </div>

      <div v-if="selectedIds.length" class="batch-bar">
        <span>已选 {{ selectedIds.length }} 项</span>
        <el-button size="small" icon="Edit" @click="openEditor(selectedChunks)">批量元数据</el-button>
        <el-button size="small" icon="Open" @click="setEnabled(selectedIds, true)">批量启用</el-button>
        <el-button size="small" icon="TurnOff" @click="setEnabled(selectedIds, false)">批量禁用</el-button>
        <el-button size="small" icon="Refresh" @click="rebuild(selectedIds)">重建向量</el-button>
      </div>

      <el-table
        ref="chunkTableRef"
        :data="knowledgeStore.chunkList"
        v-loading="knowledgeStore.chunkLoading"
        row-key="id"
        stripe
        class="chunk-table"
        @selection-change="handleSelection($event as ChunkAsset[])"
      >
        <el-table-column type="selection" width="44" fixed="left" />
        <el-table-column label="摘要" min-width="250" fixed="left" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="summary-cell">
              <span v-if="row.clause_title" class="clause-title">{{ row.clause_title }}</span>
              <span>{{ row.content }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="document_name" label="文档" min-width="170" show-overflow-tooltip />
        <el-table-column prop="section_path" label="章节" min-width="150" show-overflow-tooltip />
        <el-table-column prop="page_number" label="页码" width="70" align="right" />
        <el-table-column label="元数据" min-width="190">
          <template #default="{ row }">
            <div class="metadata-cell">
              <el-tag
                v-for="item in metadataTags(row as ChunkAsset).slice(0, 3)"
                :key="item.id"
                size="small"
                :type="item.missing ? 'danger' : 'info'"
              >
                {{ item.missing ? '缺失' : item.text }}
              </el-tag>
              <span v-if="metadataTags(row as ChunkAsset).length === 0">--</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="char_count" label="字符数" width="80" align="right" />
        <el-table-column label="向量模型" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag v-if="row.embedding_model" size="small" type="success">{{ row.embedding_model }}</el-tag>
            <el-tag v-else size="small" type="warning">未向量化</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="recall_count" label="召回次数" width="90" align="right" />
        <el-table-column label="启用" width="76">
          <template #default="{ row }">
            <el-switch
              size="small"
              :model-value="row.enabled"
              @change="handleToggle(row as ChunkAsset, $event as boolean)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="152" fixed="right" align="center">
          <template #default="{ row }">
            <el-tooltip content="详情" placement="top">
              <el-button icon="View" circle text type="primary" @click="openDetail(row as ChunkAsset)" />
            </el-tooltip>
            <el-tooltip content="元数据" placement="top">
              <el-button icon="Edit" circle text type="primary" @click="openEditor([row as ChunkAsset])" />
            </el-tooltip>
            <el-tooltip content="重建向量" placement="top">
              <el-button icon="Refresh" circle text type="primary" @click="rebuild([row.id])" />
            </el-tooltip>
            <el-tooltip :content="row.enabled ? '禁用' : '启用'" placement="top">
              <el-button
                :icon="row.enabled ? 'TurnOff' : 'Open'"
                circle
                text
                type="warning"
                @click="handleToggle(row as ChunkAsset, !row.enabled)"
              />
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-row">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="knowledgeStore.chunkTotal"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @current-change="handlePageChange"
          @size-change="handlePageSizeChange"
        />
      </div>
    </div>

    <el-drawer v-model="drawerVisible" title="分段详情" size="min(480px, 96vw)" class="chunk-drawer">
      <div v-if="currentChunk" class="drawer-body">
        <section>
          <h4>原文</h4>
          <p>{{ currentChunk.content }}</p>
        </section>
        <section>
          <h4>定位</h4>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="文档">{{ currentChunk.document_name }}</el-descriptions-item>
            <el-descriptions-item label="章节">{{ currentChunk.section_path || '--' }}</el-descriptions-item>
            <el-descriptions-item label="页码">{{ currentChunk.page_number }}</el-descriptions-item>
            <el-descriptions-item label="序号">{{ currentChunk.seq }}</el-descriptions-item>
          </el-descriptions>
        </section>
        <section>
          <h4>质量</h4>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="字符数">{{ currentChunk.char_count }}</el-descriptions-item>
            <el-descriptions-item label="向量模型">{{ currentChunk.embedding_model || '未向量化' }}</el-descriptions-item>
            <el-descriptions-item label="召回次数">{{ currentChunk.recall_count }}</el-descriptions-item>
            <el-descriptions-item label="命中记录">
              {{ currentChunk.recall_count > 0 ? `历史召回 ${currentChunk.recall_count} 次` : '暂无命中记录' }}
            </el-descriptions-item>
          </el-descriptions>
        </section>
        <section>
          <div class="section-title-row">
            <h4>元数据</h4>
            <el-button size="small" icon="Edit" @click="openEditor([currentChunk])">编辑</el-button>
          </div>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item
              v-for="(value, key) in currentChunk.metadata"
              :key="String(key)"
              :label="metadataLabel(String(key))"
            >
              {{ formatMetadata(value) || '--' }}
            </el-descriptions-item>
          </el-descriptions>
        </section>
      </div>
    </el-drawer>

    <MetadataEditor
      v-model:visible="editorVisible"
      scope="chunk"
      :ids="editorIds"
      :fields="chunkFields"
      :initial-metadata="editorMetadata"
      :mode="editorMode"
      :saving="metadataSaving"
      @save="saveMetadata"
    />
  </section>
</template>

<style lang="scss" scoped>
.segments-tab {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.document-panel,
.chunk-panel {
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 16px;
}

.panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.document-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 520px;
  overflow: auto;
  margin-top: 10px;
}

.document-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 34px;
  padding: 6px 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--el-text-color-regular);
  cursor: pointer;
  text-align: left;

  &:hover {
    background: var(--el-fill-color-light);
  }

  &.active {
    background: var(--el-color-primary-light-9);
    color: var(--el-color-primary);
  }

  &.disabled .document-name {
    color: var(--el-text-color-secondary);
  }
}

.document-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.document-count {
  flex: none;
  margin-left: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.filter-bar,
.metadata-filter-bar,
.batch-bar,
.pagination-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.filter-bar {
  margin-bottom: 12px;
}

.metadata-filter-bar {
  margin-bottom: 16px;
}

.keyword-input {
  width: 240px;
}

.metadata-filter {
  width: 160px;
}

.batch-bar {
  padding: 8px 10px;
  margin-bottom: 12px;
  border-radius: 6px;
  background: var(--el-color-primary-light-9);
  color: var(--el-text-color-regular);
  font-size: 13px;
}

.summary-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;

  .clause-title {
    color: var(--el-text-color-secondary);
    font-size: 12px;
  }
}

.metadata-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.pagination-row {
  justify-content: flex-end;
  padding-top: 14px;
}

.drawer-body {
  display: flex;
  flex-direction: column;
  gap: 18px;

  h4 {
    margin: 0 0 8px;
    color: var(--el-text-color-primary);
    font-size: 14px;
  }

  p {
    margin: 0;
    white-space: pre-wrap;
    line-height: 1.7;
    color: var(--el-text-color-regular);
  }
}

.section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

@media (max-width: 768px) {
  .segments-tab {
    grid-template-columns: 1fr;
  }

  .document-list {
    max-height: 220px;
  }

  .keyword-input,
  .metadata-filter,
  .filter-bar :deep(.el-segmented) {
    width: 100%;
  }

  .pagination-row {
    justify-content: flex-start;
  }
}
</style>
