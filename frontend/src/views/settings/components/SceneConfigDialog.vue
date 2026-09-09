<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { Scene } from '@/types/settings'

interface Props {
  visible: boolean
  data?: Scene | null
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  data: null
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [data: Scene]
}>()

const formRef = ref()
const loading = ref(false)

const form = reactive({
  id: '',
  name: '',
  description: '',
  config: {
    chunk_size: 512,
    top_k: 5,
    system_prompt: ''
  }
})

const rules = {
  name: [
    { required: true, message: '请输入场景名称', trigger: 'blur' },
    { min: 2, max: 50, message: '名称长度为 2-50 个字符', trigger: 'blur' }
  ],
  description: [
    { required: true, message: '请输入场景描述', trigger: 'blur' },
    { min: 5, max: 200, message: '描述长度为 5-200 个字符', trigger: 'blur' }
  ],
  'config.chunk_size': [
    { required: true, message: '请输入分块大小', trigger: 'blur' }
  ],
  'config.top_k': [
    { required: true, message: '请输入召回数量', trigger: 'blur' }
  ],
  'config.system_prompt': [
    { required: true, message: '请输入系统提示词', trigger: 'blur' }
  ]
}

// 监听 visible 变化，重置表单
watch(() => props.visible, (val) => {
  if (val) {
    if (props.data) {
      // 编辑模式，填充数据
      form.id = props.data.id
      form.name = props.data.name
      form.description = props.data.description
      form.config = { ...props.data.config }
    } else {
      // 新建模式，重置表单
      form.id = ''
      form.name = ''
      form.description = ''
      form.config = {
        chunk_size: 512,
        top_k: 5,
        system_prompt: ''
      }
    }
  }
})

function handleClose() {
  emit('update:visible', false)
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true

  try {
    const sceneData: Scene = {
      id: form.id || 'scene' + Date.now(),
      name: form.name,
      description: form.description,
      config: { ...form.config }
    }
    emit('submit', sceneData)
    emit('update:visible', false)
  } catch (error: any) {
    ElMessage.error(error.message || '保存失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="data?.id ? '编辑场景' : '新建场景'"
    width="600px"
    :close-on-click-modal="false"
    @update:model-value="handleClose"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="100px"
    >
      <el-form-item label="场景名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入场景名称" maxlength="50" show-word-limit />
      </el-form-item>

      <el-form-item label="场景描述" prop="description">
        <el-input
          v-model="form.description"
          type="textarea"
          placeholder="请输入场景描述"
          :rows="2"
          maxlength="200"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="分块大小" prop="config.chunk_size">
        <el-input-number
          v-model="form.config.chunk_size"
          :min="128"
          :max="4096"
          :step="64"
          placeholder="512"
          style="width: 100%"
        />
        <div class="form-tip">知识库文档切分的块大小（字符数）</div>
      </el-form-item>

      <el-form-item label="召回数量" prop="config.top_k">
        <el-input-number
          v-model="form.config.top_k"
          :min="1"
          :max="20"
          :step="1"
          placeholder="5"
          style="width: 100%"
        />
        <div class="form-tip">向量检索时返回的相关文档块数量</div>
      </el-form-item>

      <el-form-item label="系统提示词" prop="config.system_prompt">
        <el-input
          v-model="form.config.system_prompt"
          type="textarea"
          placeholder="请输入系统提示词"
          :rows="6"
          maxlength="2000"
          show-word-limit
        />
        <div class="form-tip">指导 AI 如何回答问题的提示词</div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">
        确定
      </el-button>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
.form-tip {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}
</style>
