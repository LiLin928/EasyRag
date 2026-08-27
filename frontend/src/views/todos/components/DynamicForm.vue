<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { UploadFile } from 'element-plus'
import type { TodoFormField } from '@/types/todo'

interface Props {
  schema: TodoFormField[]
  modelValue?: Record<string, unknown>
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, unknown>]
  validate: [valid: boolean, data: Record<string, unknown>]
}>()

// 表单数据
const formData = ref<Record<string, unknown>>({})

// 文件列表存储
const fileLists = ref<Record<string, UploadFile[]>>({})

// 表单引用
const formRef = ref()

// 表单验证规则
const formRules = computed(() => {
  const rules: Record<string, any> = {}
  props.schema.forEach(field => {
    if (field.required) {
      rules[field.key] = [
        {
          required: true,
          message: `请输入${field.label}`,
          trigger: field.type === 'text' || field.type === 'textarea' ? 'blur' : 'change'
        }
      ]
    }
  })
  return rules
})

// 监听外部数据变化
watch(() => props.modelValue, (newVal) => {
  if (newVal) {
    formData.value = { ...newVal }
  }
}, { immediate: true })

// 监听内部数据变化，同步给外部
watch(formData, (newVal) => {
  emit('update:modelValue', newVal)
}, { deep: true })

// 处理文件变化
function handleFileChange(file: UploadFile, fileList: UploadFile[]) {
  // 找到对应的字段key
  const fieldName = findFieldNameByFile(file)
  if (fieldName) {
    fileLists.value[fieldName] = fileList
    // 存储文件信息到formData
    formData.value[fieldName] = fileList.map(f => ({
      name: f.name,
      size: f.size,
      type: f.raw?.type
    }))
  }
}

// 根据文件对象查找字段名
function findFieldNameByFile(file: UploadFile): string | null {
  for (const field of props.schema) {
    if (field.type === 'upload') {
      const fieldFiles = fileLists.value[field.key] || []
      if (fieldFiles.some(f => f.uid === file.uid)) {
        return field.key
      }
    }
  }
  return null
}

// 获取文件列表
function getFileList(fieldKey: string): UploadFile[] {
  return fileLists.value[fieldKey] || []
}

// 验证表单
async function validate(): Promise<boolean> {
  try {
    await formRef.value?.validate()
    emit('validate', true, formData.value)
    return true
  } catch (error) {
    emit('validate', false, formData.value)
    return false
  }
}

// 暴露验证方法
defineExpose({ validate })
</script>

<template>
  <el-form
    ref="formRef"
    :model="formData"
    :rules="formRules"
    label-position="top"
    class="dynamic-form"
  >
    <el-form-item
      v-for="field in schema"
      :key="field.key"
      :label="field.label"
      :prop="field.key"
      :required="field.required"
    >
      <!-- 文本输入 -->
      <el-input
        v-if="field.type === 'text'"
        v-model="formData[field.key] as string"
        :placeholder="`请输入${field.label}`"
      />

      <!-- 文本域 -->
      <el-input
        v-else-if="field.type === 'textarea'"
        v-model="formData[field.key] as string"
        type="textarea"
        :rows="4"
        :placeholder="`请输入${field.label}`"
      />

      <!-- 下拉选择 -->
      <el-select
        v-else-if="field.type === 'select'"
        v-model="formData[field.key] as string"
        :placeholder="`请选择${field.label}`"
        style="width: 100%"
      >
        <el-option
          v-for="option in field.options"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>

      <!-- 单选框 -->
      <el-radio-group
        v-else-if="field.type === 'radio'"
        v-model="formData[field.key] as string"
      >
        <el-radio
          v-for="option in field.options"
          :key="option.value"
          :label="option.value"
        >
          {{ option.label }}
        </el-radio>
      </el-radio-group>

      <!-- 数字输入 -->
      <el-input-number
        v-else-if="field.type === 'number'"
        v-model="formData[field.key] as number"
        :placeholder="`请输入${field.label}`"
        style="width: 100%"
        :min="0"
      />

      <!-- 文件上传 -->
      <el-upload
        v-else-if="field.type === 'upload'"
        :auto-upload="false"
        :on-change="(file: UploadFile, fileList: UploadFile[]) => handleFileChange(file, fileList)"
        :file-list="getFileList(field.key)"
        drag
      >
        <el-icon :size="48"><UploadFilled /></el-icon>
        <div style="margin-top: 8px">点击或拖拽文件到此上传</div>
      </el-upload>
    </el-form-item>
  </el-form>
</template>

<style lang="scss" scoped>
.dynamic-form {
  :deep(.el-form-item__label) {
    font-weight: 500;
    color: #303133;
  }

  :deep(.el-upload-dragger) {
    padding: 20px;
  }
}
</style>
