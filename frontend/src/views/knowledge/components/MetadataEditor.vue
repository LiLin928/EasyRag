<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { MetadataField } from '@/types/knowledge'

type EditorValue = string | number | boolean | null | undefined

interface Props {
  visible: boolean
  scope: 'document' | 'chunk'
  ids: string[]
  fields: MetadataField[]
  initialMetadata?: Record<string, unknown>
  mode?: 'single' | 'batch'
  saving?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  initialMetadata: () => ({}),
  mode: 'single'
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  save: [metadata: Record<string, unknown>]
}>()

const formValues = reactive<Record<string, EditorValue>>({})

const editableFields = computed(() =>
  props.fields.filter((field) => field.visible && (!field.mapped_field || field.key === 'source'))
)

const isBatch = computed(() => props.mode === 'batch' || props.ids.length > 1)
const title = computed(() => `${isBatch.value ? '批量编辑' : '编辑'}${props.scope === 'document' ? '文档' : '分段'}元数据`)

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    Object.keys(formValues).forEach((key) => delete formValues[key])
    editableFields.value.forEach((field) => {
      if (isBatch.value) {
        formValues[field.key] = undefined
        return
      }
      const value = props.initialMetadata[field.key]
      formValues[field.key] = normalizeValue(field, value)
    })
  }
)

function normalizeValue(field: MetadataField, value: unknown): EditorValue {
  if (value === undefined || value === null) {
    return field.required ? (field.data_type === 'boolean' ? false : '') : null
  }
  return field.data_type === 'number' && typeof value === 'number'
    ? value
    : field.data_type === 'boolean' && typeof value === 'boolean'
      ? value
      : typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean'
        ? value
        : null
}

function isEmpty(value: EditorValue): boolean {
  return value === undefined || value === null || value === ''
}

function validate(): boolean {
  for (const field of editableFields.value) {
    if (!isBatch.value && field.required && !field.mapped_field && isEmpty(formValues[field.key])) {
      ElMessage.error(`请填写 ${field.name}`)
      return false
    }
    if (field.data_type === 'select' && !isEmpty(formValues[field.key])) {
      const value = formValues[field.key]
      if (typeof value !== 'string' || !field.options.includes(value)) {
        ElMessage.error(`${field.name} 不在可用选项内`)
        return false
      }
    }
  }
  return true
}

function close() {
  if (props.saving) return
  emit('update:visible', false)
}

function submit() {
  if (!validate()) return
  const metadata: Record<string, unknown> = {}
  for (const field of editableFields.value) {
    const value = formValues[field.key]
    if (isBatch.value && isEmpty(value)) continue
    metadata[field.key] = value ?? null
  }
  emit('save', metadata)
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="title"
    width="min(620px, 92vw)"
    class="metadata-editor-dialog"
    :close-on-click-modal="false"
    :show-close="!saving"
    @update:model-value="close"
  >
    <el-form label-position="top" class="metadata-form">
      <el-empty v-if="editableFields.length === 0" description="暂无可编辑字段" />
      <el-form-item
        v-for="field in editableFields"
        :key="field.id"
        :label="field.required ? `${field.name} *` : field.name"
      >
        <el-input
          v-if="field.data_type === 'string'"
          v-model="formValues[field.key] as string"
          :placeholder="isBatch ? '保持不变' : '请输入'"
          clearable
          maxlength="200"
        />
        <el-input-number
          v-else-if="field.data_type === 'number'"
          v-model="formValues[field.key] as number"
          :placeholder="isBatch ? '保持不变' : '请输入'"
          :controls="false"
          class="number-input"
        />
        <el-date-picker
          v-else-if="field.data_type === 'date'"
          v-model="formValues[field.key] as string"
          type="date"
          value-format="YYYY-MM-DD"
          :placeholder="isBatch ? '保持不变' : '请选择日期'"
          class="full-width"
        />
        <el-select
          v-else-if="field.data_type === 'select'"
          v-model="formValues[field.key] as string"
          :placeholder="isBatch ? '保持不变' : '请选择'"
          clearable
          class="full-width"
        >
          <el-option v-for="option in field.options" :key="option" :label="option" :value="option" />
        </el-select>
        <el-switch
          v-else-if="field.data_type === 'boolean' && !isBatch"
          :model-value="formValues[field.key] === true"
          @update:model-value="formValues[field.key] = $event as boolean"
        />
        <el-select
          v-else
          :model-value="typeof formValues[field.key] === 'boolean' ? formValues[field.key] : undefined"
          placeholder="保持不变"
          clearable
          class="full-width"
          @update:model-value="formValues[field.key] = $event as boolean | undefined"
        >
          <el-option label="是" :value="true" />
          <el-option label="否" :value="false" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button :disabled="saving" @click="close">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
.metadata-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;

  .el-form-item {
    margin-bottom: 16px;
  }
}

.number-input,
.full-width {
  width: 100%;
}

@media (max-width: 768px) {
  .metadata-form {
    grid-template-columns: 1fr;
  }
}
</style>
