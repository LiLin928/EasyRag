<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance } from 'element-plus'
import type { MetadataDataType, MetadataField, MetadataScope } from '@/types/knowledge'

interface Props {
  visible: boolean
  scope: MetadataScope
  field?: MetadataField | null
  existingFields: MetadataField[]
  saving?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  field: null
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  save: [payload: Omit<MetadataField, 'id' | 'kb_id' | 'built_in' | 'mapped_field'>]
}>()

interface FieldForm {
  name: string
  key: string
  data_type: MetadataDataType
  options: string[]
  default_value: unknown
  required: boolean
  filterable: boolean
  retrieval_filterable: boolean
  visible: boolean
  sort_order: number
}

const formRef = ref<FormInstance>()
const optionValue = ref('')
const form = reactive<FieldForm>({
  name: '',
  key: '',
  data_type: 'string',
  options: [],
  default_value: null,
  required: false,
  filterable: false,
  retrieval_filterable: false,
  visible: true,
  sort_order: props.existingFields.length + 1
})

const rules = {
  name: [{ required: true, message: '请输入显示名', trigger: 'blur' }],
  key: [
    { required: true, message: '请输入字段标识', trigger: 'blur' },
    { pattern: /^[a-z][a-z0-9_]{0,63}$/, message: '以小写字母开头，可含小写字母、数字、下划线', trigger: 'blur' }
  ],
  sort_order: [{ required: true, message: '请输入排序', trigger: 'blur' }]
}

const typeOptions: Array<{ label: string; value: MetadataDataType }> = [
  { label: '文本', value: 'string' },
  { label: '数字', value: 'number' },
  { label: '日期', value: 'date' },
  { label: '单选', value: 'select' },
  { label: '布尔', value: 'boolean' }
]

const duplicateKeys = computed(() =>
  new Set(
    props.existingFields
      .filter((item) => item.scope === props.scope && item.id !== props.field?.id)
      .map((item) => item.key)
  )
)

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    optionValue.value = ''
    if (props.field) {
      Object.assign(form, {
        name: props.field.name,
        key: props.field.key,
        data_type: props.field.data_type,
        options: [...props.field.options],
        default_value: props.field.default_value,
        required: props.field.required,
        filterable: props.field.filterable,
        retrieval_filterable: props.field.retrieval_filterable,
        visible: props.field.visible,
        sort_order: props.field.sort_order
      })
    } else {
      Object.assign(form, {
        name: '',
        key: '',
        data_type: 'string',
        options: [],
        default_value: null,
        required: false,
        filterable: false,
        retrieval_filterable: false,
        visible: true,
        sort_order: props.existingFields.filter((item) => item.scope === props.scope).length + 1
      })
    }
  }
)

function addOption() {
  const value = optionValue.value.trim()
  if (!value) return
  if (form.options.includes(value)) {
    ElMessage.warning('选项已存在')
    return
  }
  form.options.push(value)
  optionValue.value = ''
}

function resetDefault() {
  form.default_value = form.data_type === 'boolean' ? false : null
}

function close() {
  if (props.saving) return
  emit('update:visible', false)
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  if (!form.name.trim()) {
    ElMessage.error('请输入显示名')
    return
  }
  if (duplicateKeys.value.has(form.key)) {
    ElMessage.error('字段标识已存在')
    return
  }
  if (form.data_type === 'select' && (!form.options.length || new Set(form.options).size !== form.options.length)) {
    ElMessage.error('单选选项不能为空且不能重复')
    return
  }
  if (form.data_type !== 'select') form.options = []
  if (props.field?.built_in) {
    form.key = props.field.key
    form.data_type = props.field.data_type
  }

  emit('save', {
    name: form.name.trim(),
    key: form.key,
    scope: props.scope,
    data_type: form.data_type,
    options: [...form.options],
    default_value: form.default_value,
    required: form.required,
    filterable: form.filterable,
    retrieval_filterable: form.retrieval_filterable,
    visible: form.visible,
    sort_order: form.sort_order
  })
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="field ? '编辑元数据字段' : '新增元数据字段'"
    width="min(640px, 92vw)"
    :close-on-click-modal="false"
    :show-close="!saving"
    @update:model-value="close"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="field-form">
      <div class="form-grid">
        <el-form-item label="显示名" prop="name">
          <el-input v-model="form.name" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="标识" prop="key">
          <el-input v-model="form.key" :disabled="!!field" maxlength="64" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.data_type" :disabled="!!field" class="full-width" @change="resetDefault">
            <el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序" prop="sort_order">
          <el-input-number v-model="form.sort_order" :min="0" :max="999" class="full-width" />
        </el-form-item>
      </div>

      <el-form-item label="默认值">
        <el-input
          v-if="form.data_type === 'string'"
          v-model="form.default_value as string"
          maxlength="200"
          show-word-limit
          clearable
        />
        <el-input-number
          v-else-if="form.data_type === 'number'"
          v-model="form.default_value as number"
          :controls="false"
          class="full-width"
        />
        <el-date-picker
          v-else-if="form.data_type === 'date'"
          v-model="form.default_value as string"
          type="date"
          value-format="YYYY-MM-DD"
          class="full-width"
        />
        <el-switch v-else-if="form.data_type === 'boolean'" :model-value="form.default_value === true" @update:model-value="form.default_value = $event as boolean" />
      </el-form-item>

      <el-form-item v-if="form.data_type === 'select'" label="选项">
        <div class="option-editor">
          <el-input
            v-model="optionValue"
            placeholder="输入选项后回车"
            maxlength="50"
            @keyup.enter.prevent="addOption"
          />
          <el-button icon="Plus" @click="addOption">添加</el-button>
          <div v-if="form.options.length" class="option-tags">
            <el-tag
              v-for="option in form.options"
              :key="option"
              closable
              @close="form.options = form.options.filter((item) => item !== option)"
            >
              {{ option }}
            </el-tag>
          </div>
        </div>
      </el-form-item>

      <div class="switch-grid">
        <el-form-item label="必填">
          <el-switch v-model="form.required" :disabled="!!field?.built_in" />
        </el-form-item>
        <el-form-item label="列表筛选">
          <el-switch v-model="form.filterable" />
        </el-form-item>
        <el-form-item label="检索过滤">
          <el-switch v-model="form.retrieval_filterable" />
        </el-form-item>
        <el-form-item label="默认展示">
          <el-switch v-model="form.visible" />
        </el-form-item>
      </div>
    </el-form>
    <template #footer>
      <el-button :disabled="saving" @click="close">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
.field-form {
  .form-grid,
  .switch-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    column-gap: 16px;
  }
}

.full-width {
  width: 100%;
}

.option-editor {
  width: 100%;
  display: flex;
  gap: 8px;

  .el-input {
    flex: 1;
  }
}

.option-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

@media (max-width: 768px) {
  .form-grid,
  .switch-grid,
  .option-editor {
    grid-template-columns: 1fr;
  }

  .option-editor {
    flex-wrap: wrap;
  }
}
</style>
