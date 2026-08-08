<script setup lang="ts">
import { reactive, watch } from 'vue'

interface Props {
  data: any
  readonly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  readonly: false
})

const emit = defineEmits<{
  update: [data: any]
}>()

const form = reactive({
  ico: '🔧',
  name: '',
  desc: '',
  trigger: '',
  prompt: ''
})

const rules = {
  name: [
    { required: true, message: '请输入技能名称', trigger: 'blur' },
    { min: 2, max: 50, message: '名称长度为 2-50 个字符', trigger: 'blur' }
  ],
  desc: [
    { required: true, message: '请输入技能描述', trigger: 'blur' }
  ],
  trigger: [
    { required: true, message: '请输入触发条件', trigger: 'blur' }
  ],
  prompt: [
    { required: true, message: '请输入系统 Prompt', trigger: 'blur' }
  ]
}

const formRef = ref()

// 常用图标列表
const iconOptions = [
  '🔧', '📋', '⚠️', '📊', '🎧', '🔍', '💡', '🎯',
  '📝', '🗂️', '📌', '🔔', '⚡', '🚀', '💻', '🔬'
]

// 监听数据变化
watch(() => props.data, (data) => {
  if (data) {
    Object.assign(form, {
      ico: data.ico || '🔧',
      name: data.name || '',
      desc: data.desc || '',
      trigger: data.trigger || '',
      prompt: data.prompt || ''
    })
  }
}, { immediate: true, deep: true })

// 监听表单变化
watch(form, (newForm) => {
  emit('update', newForm)
}, { deep: true })

function validate() {
  return formRef.value?.validate()
}

defineExpose({
  validate
})
</script>

<template>
  <el-form
    ref="formRef"
    :model="form"
    :rules="rules"
    label-width="80px"
    class="basic-form"
  >
    <el-form-item label="图标">
      <div class="icon-selector">
        <div
          v-for="icon in iconOptions"
          :key="icon"
          class="icon-option"
          :class="{ active: form.ico === icon }"
          @click="!readonly && (form.ico = icon)"
        >
          {{ icon }}
        </div>
      </div>
    </el-form-item>

    <el-form-item label="名称" prop="name">
      <el-input
        v-model="form.name"
        placeholder="请输入技能名称"
        maxlength="50"
        show-word-limit
        :disabled="readonly"
      />
    </el-form-item>

    <el-form-item label="描述" prop="desc">
      <el-input
        v-model="form.desc"
        type="textarea"
        placeholder="请输入技能描述"
        :rows="2"
        maxlength="200"
        show-word-limit
        :disabled="readonly"
      />
    </el-form-item>

    <el-form-item label="触发条件" prop="trigger">
      <el-input
        v-model="form.trigger"
        type="textarea"
        placeholder="例如：当用户询问xxx时触发"
        :rows="2"
        :disabled="readonly"
      />
    </el-form-item>

    <el-form-item label="系统Prompt" prop="prompt">
      <el-input
        v-model="form.prompt"
        type="textarea"
        placeholder="请输入系统Prompt，定义AI的角色和任务"
        :rows="8"
        :disabled="readonly"
      />
    </el-form-item>
  </el-form>
</template>

<style lang="scss" scoped>
.basic-form {
  padding: 16px;
}

.icon-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.icon-option {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  border: 2px solid #e0e0e0;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    border-color: #409eff;
    background: #f0f9ff;
  }

  &.active {
    border-color: #409eff;
    background: #e6f7ff;
  }
}
</style>
