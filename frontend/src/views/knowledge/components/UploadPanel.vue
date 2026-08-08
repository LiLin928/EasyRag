<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useKnowledgeStore } from '@/stores/knowledge'

interface Props {
  kbId: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  uploaded: []
}>()

const knowledgeStore = useKnowledgeStore()

const parseMode = ref<'fast' | 'precision'>('fast')
const scene = ref('')
const uploading = ref(false)

const sceneOptions = [
  { label: '招投标', value: 'bidding' },
  { label: '合同', value: 'contract' },
  { label: '通用', value: 'general' },
  { label: '技术', value: 'tech' },
  { label: '产品', value: 'product' }
]

async function handleUpload(options: any) {
  const file = options.file as File
  const validTypes = ['pdf', 'docx', 'doc', 'xlsx', 'xls', 'md', 'txt']
  const ext = file.name.split('.').pop()?.toLowerCase()
  
  if (!ext || !validTypes.includes(ext)) {
    ElMessage.error('仅支持 PDF、Word、Excel、Markdown、TXT 格式')
    return
  }
  
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 50MB')
    return
  }
  
  uploading.value = true
  
  try {
    const tasks = await knowledgeStore.uploadFiles(
      props.kbId,
      [file],
      parseMode.value,
      scene.value || undefined
    )
    
    ElMessage.success('文件上传成功，正在解析...')
    
    // 开始轮询解析状态
    tasks.forEach(task => {
      knowledgeStore.startPolling(task.task_id, () => {
        emit('uploaded')
      })
    })
  } catch (error: any) {
    ElMessage.error(error.message || '上传失败')
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="upload-panel">
    <el-upload
      class="upload-dragger"
      drag
      :auto-upload="true"
      :show-file-list="false"
      :http-request="handleUpload"
      accept=".pdf,.doc,.docx,.xls,.xlsx,.md,.txt"
    >
      <el-icon class="upload-icon" :size="48"><UploadFilled /></el-icon>
      <div class="upload-text">
        拖拽文件到此处，或<em>点击上传</em>
      </div>
      <template #tip>
        <div class="upload-tip">
          支持 PDF、Word、Excel、Markdown、TXT 格式，单个文件不超过 50MB
        </div>
      </template>
    </el-upload>
    
    <div class="upload-options">
      <el-form label-width="80px" size="small">
        <el-form-item label="解析模式">
          <el-radio-group v-model="parseMode">
            <el-radio value="fast">快速模式</el-radio>
            <el-radio value="precision">精准模式</el-radio>
          </el-radio-group>
        </el-form-item>
        
        <el-form-item label="关联场景">
          <el-select v-model="scene" placeholder="选择场景（可选）" clearable>
            <el-option
              v-for="item in sceneOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.upload-panel {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
}

.upload-dragger {
  :deep(.el-upload-dragger) {
    width: 100%;
    height: 120px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }
  
  .upload-icon {
    color: #409eff;
    margin-bottom: 8px;
  }
  
  .upload-text {
    color: #606266;
    font-size: 14px;
    
    em {
      color: #409eff;
      font-style: normal;
    }
  }
  
  .upload-tip {
    text-align: center;
    color: #909399;
    font-size: 12px;
    margin-top: 8px;
  }
}

.upload-options {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}
</style>
