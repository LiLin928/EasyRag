<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useKnowledgeStore } from '@/stores/knowledge'
import UploadPanel from './UploadPanel.vue'
import DocumentTable from './DocumentTable.vue'
import MetadataEditor from './MetadataEditor.vue'
import ConfirmDelete from '@/components/common/ConfirmDelete.vue'
import type { DocumentAsset, MetadataField } from '@/types/knowledge'

interface Props {
  kbId: string
}

const props = defineProps<Props>()

const router = useRouter()
const knowledgeStore = useKnowledgeStore()

type StatusFilter = 'all' | DocumentAsset['status']
type EnabledFilter = 'all' | boolean
type SortFilter = 'created_desc' | 'name_asc' | 'name_desc' | 'chunk_count_desc' | 'recall_count_desc'

const keyword = ref('')
const statusFilter = ref<StatusFilter>('all')
const enabledFilter = ref<EnabledFilter>('all')
const sortFilter = ref<SortFilter>('created_desc')
const metadataFilters = ref<Record<string, unknown>>({})
const page = ref(1)
const pageSize = ref(20)
const selectedIds = ref<string[]>([])
const editorVisible = ref(false)
const editorIds = ref<string[]>([])
const editorMetadata = ref<Record<string, unknown>>({})
const editorMode = ref<'single' | 'batch'>('single')
const metadataSaving = ref(false)
const initialized = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const documentFields = computed<MetadataField[]>(() =>
  knowledgeStore.metadataFields.filter(
    (field) => field.kb_id === props.kbId && field.scope === 'document' && field.filterable && field.visible
  )
)
const allDocumentFields = computed<MetadataField[]>(() =>
  knowledgeStore.metadataFields.filter((field) => field.kb_id === props.kbId && field.scope === 'document')
)
const selectedDocuments = computed<DocumentAsset[]>(() =>
  knowledgeStore.docList.filter((item) => selectedIds.value.includes(item.id))
)

watch(keyword, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    void load()
  }, 300)
})

watch([statusFilter, enabledFilter, sortFilter], () => {
  if (!initialized.value) return
  page.value = 1
  void load()
})

watch(metadataFilters, () => {
  if (!initialized.value) return
  page.value = 1
  void load()
}, { deep: true })

initialized.value = true

watch(() => props.kbId, () => {
  keyword.value = ''
  statusFilter.value = 'all'
  enabledFilter.value = 'all'
  sortFilter.value = 'created_desc'
  metadataFilters.value = {}
  page.value = 1
  selectedIds.value = []
})

onMounted(() => {
  if (!hasDefaultDocumentFilter()) void load()
})

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
})

function hasDefaultDocumentFilter(): boolean {
  const filter = knowledgeStore.documentFilter
  const keys = Object.keys(filter).filter((key) => key !== 'keyword')
  return !filter.keyword && keys.length === 1 && keys[0] === 'sort' && filter.sort === 'created_desc'
}

function hasFilterValue(value: unknown): boolean {
  return value !== undefined && value !== null && value !== '' && (!Array.isArray(value) || value.length > 0)
}

async function load(): Promise<void> {
  const filter: Record<string, unknown> = {
    keyword: keyword.value.trim() || undefined,
    sort: sortFilter.value
  }
  if (statusFilter.value !== 'all') filter.status = statusFilter.value
  if (enabledFilter.value !== 'all') filter.enabled = enabledFilter.value
  const metadata = Object.fromEntries(
    Object.entries(metadataFilters.value).filter(([, value]) => hasFilterValue(value))
  )
  if (Object.keys(metadata).length) filter.document_metadata = JSON.stringify(metadata)
  await knowledgeStore.loadDocuments(props.kbId, page.value, pageSize.value, filter)
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

function openEditor(documents: DocumentAsset[]): void {
  editorIds.value = documents.map((item) => item.id)
  editorMode.value = documents.length > 1 ? 'batch' : 'single'
  editorMetadata.value = documents.length === 1 ? { ...documents[0].metadata } : {}
  editorVisible.value = true
}

function handleToggle(document: DocumentAsset, enabled: boolean): void {
  void setEnabled([document.id], enabled)
}

async function saveMetadata(metadata: Record<string, unknown>): Promise<void> {
  if (metadataSaving.value) return
  metadataSaving.value = true
  try {
    await knowledgeStore.saveDocumentMetadata(props.kbId, editorIds.value, metadata)
    editorVisible.value = false
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
        `确定要${enabled ? '启用' : '禁用'}选中的 ${ids.length} 个文档吗？`,
        '批量操作确认',
        { confirmButtonText: enabled ? '启用' : '禁用', cancelButtonText: '取消', type: 'warning' }
      )
    }
    await knowledgeStore.setDocumentEnabled(props.kbId, ids, enabled)
    ElMessage.success('状态已更新')
    selectedIds.value = []
  } catch (error) {
    // Cancel keeps the current status.
  }
}

async function rebuild(doc: DocumentAsset): Promise<void> {
  await knowledgeStore.queueReembedding(props.kbId, [doc.id], [])
  ElMessage.success('索引重建已排队')
}

async function rebuildSelected(): Promise<void> {
  const documentIds = selectedIds.value
  await knowledgeStore.queueReembedding(props.kbId, documentIds, [])
  ElMessage.success('索引重建已排队')
}

async function remove(doc: DocumentAsset): Promise<void> {
  await knowledgeStore.deleteDocument(props.kbId, doc.id)
  selectedIds.value = selectedIds.value.filter((id) => id !== doc.id)
  ElMessage.success('删除成功')
  await knowledgeStore.loadKbDetail(props.kbId)
  await load()
}

async function removeSelected(): Promise<void> {
  for (const id of selectedIds.value) {
    await knowledgeStore.deleteDocument(props.kbId, id)
  }
  selectedIds.value = []
  ElMessage.success('删除成功')
  await knowledgeStore.loadKbDetail(props.kbId)
  await load()
}

function view(doc: DocumentAsset): void {
  router.push(`/knowledge/${props.kbId}/docs/${doc.id}`)
}

async function refreshAfterUpload(): Promise<void> {
  await knowledgeStore.loadKbDetail(props.kbId)
  await load()
}
</script>

<template>
  <section class="documents-tab">
    <UploadPanel :kb-id="kbId" @uploaded="refreshAfterUpload" />

    <div class="table-panel">
      <div class="filter-bar">
        <el-input
          v-model="keyword"
          class="keyword-input"
          placeholder="搜索文档"
          clearable
          @clear="load"
        >
          <template #append>
            <el-button icon="Search" @click="load" />
          </template>
        </el-input>
        <el-segmented
          v-model="statusFilter"
          :options="[
            { label: '全部', value: 'all' },
            { label: '等待中', value: 'pending' },
            { label: '解析中', value: 'parsing' },
            { label: '已完成', value: 'done' },
            { label: '失败', value: 'failed' }
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
        <el-select v-model="sortFilter" class="sort-select">
          <el-option label="上传时间优先" value="created_desc" />
          <el-option label="文档名升序" value="name_asc" />
          <el-option label="文档名降序" value="name_desc" />
          <el-option label="分段数优先" value="chunk_count_desc" />
          <el-option label="召回次数优先" value="recall_count_desc" />
        </el-select>
      </div>

      <div v-if="documentFields.length" class="metadata-filter-bar">
        <template v-for="field in documentFields" :key="field.id">
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
        <span class="batch-count">已选 {{ selectedIds.length }} 项</span>
        <el-button size="small" icon="Edit" @click="openEditor(selectedDocuments)">
          批量元数据
        </el-button>
        <el-button size="small" icon="Open" @click="setEnabled(selectedIds, true)">批量启用</el-button>
        <el-button size="small" icon="TurnOff" @click="setEnabled(selectedIds, false)">批量禁用</el-button>
        <el-button size="small" icon="Refresh" @click="rebuildSelected">重建索引</el-button>
        <ConfirmDelete message="确定删除选中文档及其分段吗？" @confirm="removeSelected" />
      </div>

      <DocumentTable
        :kb-id="kbId"
        :documents="knowledgeStore.docList"
        :loading="knowledgeStore.docLoading"
        :fields="allDocumentFields"
        :selected-ids="selectedIds"
        @selection-change="selectedIds = $event"
        @view="view"
        @metadata="openEditor([$event])"
        @rebuild="rebuild"
        @toggle="handleToggle"
        @delete="remove"
      />

      <div class="pagination-row">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="knowledgeStore.docTotal"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @current-change="handlePageChange"
          @size-change="handlePageSizeChange"
        />
      </div>
    </div>

    <MetadataEditor
      v-model:visible="editorVisible"
      :scope="'document'"
      :ids="editorIds"
      :fields="allDocumentFields"
      :initial-metadata="editorMetadata"
      :mode="editorMode"
      :saving="metadataSaving"
      @save="saveMetadata"
    />
  </section>
</template>

<style lang="scss" scoped>
.documents-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.table-panel,
:deep(.upload-panel) {
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 16px;
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
  width: 260px;
}

.sort-select {
  width: 160px;
}

.metadata-filter {
  width: 170px;
}

.batch-bar {
  padding: 8px 10px;
  margin-bottom: 12px;
  border-radius: 6px;
  background: var(--el-color-primary-light-9);

  .batch-count {
    color: var(--el-text-color-regular);
    font-size: 13px;
  }
}

.pagination-row {
  justify-content: flex-end;
  padding-top: 14px;
}

@media (max-width: 768px) {
  .keyword-input,
  .sort-select,
  .metadata-filter {
    width: 100%;
  }

  .filter-bar :deep(.el-segmented) {
    width: 100%;
  }

  .pagination-row {
    justify-content: flex-start;
  }
}
</style>
