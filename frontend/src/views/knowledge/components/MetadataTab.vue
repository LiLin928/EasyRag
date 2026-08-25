<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useKnowledgeStore } from '@/stores/knowledge'
import ConfirmDelete from '@/components/common/ConfirmDelete.vue'
import MetadataFieldDialog from './MetadataFieldDialog.vue'
import type { MetadataField, MetadataFieldPayload, MetadataScope } from '@/types/knowledge'

interface Props {
  kbId: string
}

const props = defineProps<Props>()
const knowledgeStore = useKnowledgeStore()

const scope = ref<MetadataScope>('document')
const dialogVisible = ref(false)
const editingField = ref<MetadataField | null>(null)
const fieldSaving = ref(false)
const savingCount = ref(0)
const draggingField = ref<MetadataField | null>(null)

const fields = computed<MetadataField[]>(() =>
  knowledgeStore.metadataFields
    .filter((field) => field.kb_id === props.kbId && field.scope === scope.value)
    .sort((a, b) => a.sort_order - b.sort_order)
)

async function patchField(field: MetadataField, payload: Partial<MetadataField>): Promise<void> {
  savingCount.value += 1
  try {
    await knowledgeStore.updateMetadataField(props.kbId, field.id, payload)
  } finally {
    savingCount.value -= 1
  }
}

function openCreate(): void {
  editingField.value = null
  dialogVisible.value = true
}

function openEdit(field: MetadataField): void {
  editingField.value = field
  dialogVisible.value = true
}

async function saveField(payload: MetadataFieldPayload): Promise<void> {
  if (fieldSaving.value) return
  if (editingField.value) {
    const current = editingField.value
    const optionsChanged = JSON.stringify(current.options) !== JSON.stringify(payload.options)
    const retrievalChanged = current.retrieval_filterable !== payload.retrieval_filterable
    if (optionsChanged || retrievalChanged) {
      try {
        await ElMessageBox.confirm(
          '该字段会影响检索过滤或筛选选项，保存后将立即生效。',
          '生效确认',
          { confirmButtonText: '保存并生效', cancelButtonText: '取消', type: 'warning' }
        )
      } catch (error) {
        return
      }
    }
    const payloadForApi: Partial<MetadataField> = {
      name: payload.name,
      options: payload.options,
      default_value: payload.default_value,
      required: payload.required,
      filterable: payload.filterable,
      retrieval_filterable: payload.retrieval_filterable,
      visible: payload.visible,
      sort_order: payload.sort_order
    }
    fieldSaving.value = true
    try {
      await patchField(current, payloadForApi)
      dialogVisible.value = false
      ElMessage.success('字段已更新')
    } catch (error) {
      // Keep the dialog open so the failed form remains editable.
    } finally {
      fieldSaving.value = false
    }
    return
  }

  fieldSaving.value = true
  try {
    await knowledgeStore.saveMetadataField(props.kbId, payload)
    dialogVisible.value = false
    ElMessage.success('字段已创建')
  } catch (error) {
    // Keep the dialog open so the failed form remains editable.
  } finally {
    fieldSaving.value = false
  }
}

async function updateFlag(
  field: MetadataField,
  key: 'filterable' | 'retrieval_filterable' | 'visible',
  value: boolean
): Promise<void> {
  if (key === 'retrieval_filterable') {
    try {
      await ElMessageBox.confirm(
        `${value ? '开启' : '关闭'}后该字段的检索过滤能力将立即生效。`,
        '生效确认',
        {
          confirmButtonText: value ? '开启并保存' : '关闭并保存',
          cancelButtonText: '取消',
          type: 'warning'
        }
      )
    } catch (error) {
      return
    }
  }
  await patchField(field, { [key]: value })
  ElMessage.success('字段已更新')
}

async function removeField(field: MetadataField): Promise<void> {
  const impact = await knowledgeStore.removeMetadataField(props.kbId, field.id, false)
  if (!impact.success) {
    try {
      await ElMessageBox.confirm(
        `该字段已有 ${impact.affected_count} 个值，删除后将同时清除这些值。`,
        '强制删除确认',
        { confirmButtonText: '强制删除', cancelButtonText: '取消', type: 'warning' }
      )
      await knowledgeStore.removeMetadataField(props.kbId, field.id, true)
    } catch (error) {
      return
    }
  }
  ElMessage.success('字段已删除')
}

function handleDragStart(field: MetadataField): void {
  draggingField.value = field
}

async function handleDrop(target: MetadataField): Promise<void> {
  const source = draggingField.value
  draggingField.value = null
  if (!source || source.id === target.id) return

  const nextFields = [...fields.value]
  const sourceIndex = nextFields.findIndex((item) => item.id === source.id)
  const targetIndex = nextFields.findIndex((item) => item.id === target.id)
  if (sourceIndex < 0 || targetIndex < 0) return
  nextFields.splice(sourceIndex, 1)
  nextFields.splice(targetIndex, 0, source)

  savingCount.value += 1
  try {
    await knowledgeStore.reorderMetadataFields(
      props.kbId,
      nextFields.map((field) => field.id)
    )
    ElMessage.success('排序已保存')
  } finally {
    savingCount.value -= 1
  }
}
</script>

<template>
  <section class="metadata-tab">
    <div class="toolbar">
      <el-segmented
        v-model="scope"
        :options="[
          { label: '文档', value: 'document' },
          { label: '分段', value: 'chunk' }
        ]"
      />
      <el-button type="primary" icon="Plus" @click="openCreate">新增字段</el-button>
    </div>

    <el-table
      :data="fields"
      row-key="id"
      stripe
      class="metadata-table"
      v-loading="savingCount > 0"
    >
      <el-table-column label="排序" width="72" align="center">
        <template #default="{ row }">
          <el-icon
            class="drag-handle"
            draggable="true"
            @dragstart="handleDragStart(row as MetadataField)"
            @dragover.prevent
            @drop="handleDrop(row as MetadataField)"
          >
            <Rank />
          </el-icon>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="显示名" min-width="130" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="name-cell">
            {{ row.name }}
            <el-tag v-if="row.built_in" size="small" type="info">内置</el-tag>
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="key" label="key" min-width="150" show-overflow-tooltip />
      <el-table-column label="类型" width="84">
        <template #default="{ row }">
          {{ row.data_type === 'string' ? '文本' : row.data_type === 'number' ? '数字' : row.data_type === 'date' ? '日期' : row.data_type === 'select' ? '单选' : '布尔' }}
        </template>
      </el-table-column>
      <el-table-column label="必填" width="76" align="center">
        <template #default="{ row }">
          <el-switch :model-value="row.required" disabled />
        </template>
      </el-table-column>
      <el-table-column label="列表筛选" width="92" align="center">
        <template #default="{ row }">
          <el-switch
            :model-value="row.filterable"
            @change="updateFlag(row as MetadataField, 'filterable', $event as boolean)"
          />
        </template>
      </el-table-column>
      <el-table-column label="检索过滤" width="92" align="center">
        <template #default="{ row }">
          <el-switch
            :model-value="row.retrieval_filterable"
            @change="updateFlag(row as MetadataField, 'retrieval_filterable', $event as boolean)"
          />
        </template>
      </el-table-column>
      <el-table-column label="默认展示" width="92" align="center">
        <template #default="{ row }">
          <el-switch
            :model-value="row.visible"
            @change="updateFlag(row as MetadataField, 'visible', $event as boolean)"
          />
        </template>
      </el-table-column>
      <el-table-column label="启用" width="76" align="center">
        <template #default>
          <el-tag size="small" type="success">启用</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right" align="center">
        <template #default="{ row }">
          <el-tooltip content="编辑" placement="top">
            <el-button icon="Edit" circle text type="primary" @click="openEdit(row as MetadataField)" />
          </el-tooltip>
          <ConfirmDelete
            v-if="!row.built_in"
            :message="`确定删除字段“${row.name}”吗？`"
            @confirm="removeField(row as MetadataField)"
          />
        </template>
      </el-table-column>
    </el-table>

    <MetadataFieldDialog
      v-model:visible="dialogVisible"
      :scope="scope"
      :field="editingField"
      :existing-fields="knowledgeStore.metadataFields"
      :saving="fieldSaving"
      @save="saveField"
    />
  </section>
</template>

<style lang="scss" scoped>
.metadata-tab {
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 16px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.name-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.drag-handle {
  color: var(--el-text-color-secondary);
  cursor: move;

  &:hover {
    color: var(--el-color-primary);
  }
}

:deep(.el-button + .el-button) {
  margin-left: 4px;
}

@media (max-width: 768px) {
  .toolbar {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
