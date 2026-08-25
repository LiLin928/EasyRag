<script setup lang="ts">
import { ref, watch } from 'vue'
import StatusChip from '@/components/common/StatusChip.vue'
import FileIcon from '@/components/common/FileIcon.vue'
import ConfirmDelete from '@/components/common/ConfirmDelete.vue'
import type { DocumentAsset, MetadataField } from '@/types/knowledge'

interface Props {
  kbId: string
  documents: DocumentAsset[]
  loading: boolean
  fields: MetadataField[]
  selectedIds: string[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'selection-change': [ids: string[]]
  view: [document: DocumentAsset]
  metadata: [document: DocumentAsset]
  rebuild: [document: DocumentAsset]
  toggle: [document: DocumentAsset, enabled: boolean]
  delete: [document: DocumentAsset]
}>()

const tableRef = ref()

watch(
  () => props.selectedIds,
  (ids) => {
    if (ids.length === 0) tableRef.value?.clearSelection()
  }
)

const statusMap: Record<DocumentAsset['status'], { type: 'ok' | 'err' | 'warn' | 'run' | 'wait' | 'gray'; label: string }> = {
  done: { type: 'ok', label: '已完成' },
  parsing: { type: 'run', label: '解析中' },
  failed: { type: 'err', label: '失败' },
  pending: { type: 'wait', label: '等待中' }
}

function getStatusInfo(status: DocumentAsset['status']) {
  return statusMap[status]
}

function formatSize(size: number): string {
  if (size >= 1024 * 1024) return (size / 1024 / 1024).toFixed(1) + ' MB'
  if (size >= 1024) return (size / 1024).toFixed(1) + ' KB'
  return size + ' B'
}

function formatMetadata(value: unknown): string {
  if (value === null || value === undefined || value === '') return ''
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function metadataItems(document: DocumentAsset, fields: MetadataField[]) {
  return fields
    .filter((field) => field.visible)
    .map((field) => ({
      field,
      value: document.metadata[field.key],
      missing: field.required && !field.mapped_field && document.metadata[field.key] === undefined
    }))
}

function handleSelection(rows: DocumentAsset[]): void {
  emit('selection-change', rows.map((row) => row.id))
}
</script>

<template>
  <el-table
    ref="tableRef"
    :data="documents"
    v-loading="loading"
    row-key="id"
    stripe
    class="document-table"
    @selection-change="handleSelection($event as DocumentAsset[])"
  >
    <el-table-column type="selection" width="44" fixed="left" />
    <el-table-column label="文件" min-width="220" fixed="left" show-overflow-tooltip>
      <template #default="{ row }">
        <div class="doc-name">
          <FileIcon :ext="row.ext" :size="28" />
          <span class="name-text">{{ row.name }}</span>
        </div>
      </template>
    </el-table-column>
    <el-table-column label="大小" width="100">
      <template #default="{ row }">{{ formatSize(row.size) }}</template>
    </el-table-column>
    <el-table-column label="状态" width="130">
      <template #default="{ row }">
        <div class="status-cell">
          <StatusChip :type="getStatusInfo(row.status).type" :label="getStatusInfo(row.status).label" />
          <el-progress
            v-if="row.status === 'parsing' && row.pct"
            :percentage="row.pct"
            :stroke-width="4"
            :show-text="false"
          />
        </div>
      </template>
    </el-table-column>
    <el-table-column prop="chunk_count" label="分段数" width="80" align="right" />
    <el-table-column label="元数据" min-width="210">
      <template #default="{ row }">
        <div class="metadata-cell">
          <template v-for="item in metadataItems(row as DocumentAsset, fields)" :key="item.field.id">
            <el-tag v-if="item.missing" size="small" type="danger" class="metadata-tag">
              {{ item.field.name }}缺失
            </el-tag>
            <el-tag v-else-if="formatMetadata(item.value)" size="small" type="info" class="metadata-tag">
              {{ formatMetadata(item.value) }}
            </el-tag>
          </template>
          <span v-if="metadataItems(row as DocumentAsset, fields).length === 0" class="muted">--</span>
        </div>
      </template>
    </el-table-column>
    <el-table-column prop="recall_count" label="召回次数" width="90" align="right" />
    <el-table-column label="启用" width="76">
      <template #default="{ row }">
        <el-switch
          size="small"
          :model-value="row.enabled"
          @change="emit('toggle', row as DocumentAsset, $event as boolean)"
        />
      </template>
    </el-table-column>
    <el-table-column prop="created_at" label="上传时间" width="160" show-overflow-tooltip />
    <el-table-column label="操作" width="205" fixed="right" align="center">
      <template #default="{ row }">
        <el-tooltip content="详情" placement="top">
          <el-button icon="View" circle text type="primary" @click="emit('view', row as DocumentAsset)" />
        </el-tooltip>
        <el-tooltip content="元数据" placement="top">
          <el-button icon="Edit" circle text type="primary" @click="emit('metadata', row as DocumentAsset)" />
        </el-tooltip>
        <el-tooltip content="重建索引" placement="top">
          <el-button icon="Refresh" circle text type="primary" @click="emit('rebuild', row as DocumentAsset)" />
        </el-tooltip>
        <el-tooltip :content="row.enabled ? '禁用' : '启用'" placement="top">
          <el-button
            :icon="row.enabled ? 'TurnOff' : 'Open'"
            circle
            text
            type="warning"
            @click="emit('toggle', row as DocumentAsset, !row.enabled)"
          />
        </el-tooltip>
        <ConfirmDelete :message="`确定删除“${row.name}”吗？`" @confirm="emit('delete', row as DocumentAsset)" />
      </template>
    </el-table-column>
  </el-table>
</template>

<style lang="scss" scoped>
.doc-name {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 10px;

  .name-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.status-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.metadata-cell {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.metadata-tag {
  max-width: 100%;
}

.muted {
  color: var(--el-text-color-secondary);
}

:deep(.el-button + .el-button) {
  margin-left: 4px;
}

:deep(.el-button--small) {
  margin-left: 4px;
}
</style>
