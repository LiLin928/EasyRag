<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { KnowledgeBase } from '@/types/knowledge'

interface Props {
  visible: boolean
  data?: KnowledgeBase | null
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  data: null
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [data: Partial<KnowledgeBase>]
}>()

const formRef = ref()
const loading = ref(false)

const form = reactive({
  name: '',
  desc: '',
  scene: '',
  cover: '#409eff'
})

const rules = {
  name: [
    { required: true, message: '请输入知识库名称', trigger: 'blur' },
    { min: 2, max: 50, message: '名称长度为 2-50 个字符', trigger: 'blur' }
  ]
}

const sceneOptions = [
  { label: '招投标', value: 'bidding' },
  { label: '合同', value: 'contract' },
  { label: '通用', value: 'general' },
  { label: '技术', value: 'tech' },
  { label: '产品', value: 'product' }
]

const coverColors = [
  '#409eff',
  '#67c23a',
  '#e6a23c',
  '#f56c6c',
  '#909399',
  '#9c27b0'
]

// 监听 visible 变化，重置表单
watch(() => props.visible, (val) => {
  if (val) {
    if (props.data) {
      // 编辑模式，填充数据
      form.name = props.data.name
      form.desc = props.data.desc
      form.scene = props.data.scene
      form.cover = props.data.cover || '#409eff'
    } else {
      // 新建模式，重置表单
      form.name = ''
      form.desc = ''
      form.scene = ''
      form.cover = '#409eff'
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
    emit('submit', { ...form })
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
    :title="data ? '编辑知识库' : '新建知识库'"
    width="500px"
    :close-on-click-modal="false"
    @update:model-value="handleClose"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="80px"
    >
      <el-form-item label="名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入知识库名称" maxlength="50" show-word-limit />
      </el-form-item>
      
      <el-form-item label="描述" prop="desc">
        <el-input
          v-model="form.desc"
          type="textarea"
          placeholder="请输入知识库描述"
          :rows="3"
          maxlength="200"
          show-word-limit
        />
      </el-form-item>
      
      <el-form-item label="场景" prop="scene">
        <el-select v-model="form.scene" placeholder="选择关联场景" clearable>
          <el-option
            v-for="item in sceneOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      
      <el-form-item label="封面色" prop="cover">
        <div class="cover-colors">
          <div
            v-for="color in coverColors"
            :key="color"
            class="color-item"
            :class="{ active: form.cover === color }"
            :style="{ backgroundColor: color }"
            @click="form.cover = color"
          />
        </div>
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
.cover-colors {
  display: flex;
  gap: 8px;
  
  .color-item {
    width: 32px;
    height: 32px;
    border-radius: 4px;
    cursor: pointer;
    transition: transform 0.2s;
    
    &:hover {
      transform: scale(1.1);
    }
    
    &.active {
      box-shadow: 0 0 0 2px #fff, 0 0 0 4px #409eff;
    }
  }
}
</style>
