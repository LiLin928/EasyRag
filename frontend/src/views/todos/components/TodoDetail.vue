<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import DynamicForm from './DynamicForm.vue'
import CountdownBadge from './CountdownBadge.vue'
import type { Todo } from '@/types/todo'

interface Props {
  data: Todo
}

const props = defineProps<Props>()

const emit = defineEmits<{
  submit: [id: string, formData: Record<string, unknown>]
  reject: [id: string]
  close: []
}>()

// 表单数据
const formData = ref<Record<string, unknown>>({})
const formRef = ref()

// 是否超时
const isTimeout = computed(() => {
  return props.data.status === 'pending' && props.data.deadline !== undefined && props.data.deadline <= 0
})

// 是否可以提交
const canSubmit = computed(() => {
  return props.data.status === 'pending' && !isTimeout.value
})

// 处理提交
async function handleSubmit() {
  if (!formRef.value) {
    ElMessage.error('表单未初始化')
    return
  }

  const valid = await formRef.value.validate()
  if (!valid) {
    ElMessage.error('请检查表单填写')
    return
  }

  emit('submit', props.data.id, formData.value)
}

// 处理驳回
function handleReject() {
  emit('reject', props.data.id)
}

// 关闭详情
function handleClose() {
  emit('close')
}
</script>

<template>
  <div class="todo-detail">
    <div class="detail-header">
      <div class="header-left">
        <h3 class="detail-title">{{ data.title }}</h3>
        <div class="detail-source">
          <el-icon><Share /></el-icon>
          <span>{{ data.source }}</span>
        </div>
      </div>
      <div class="header-right">
        <CountdownBadge
          v-if="data.status === 'pending' && data.deadline !== undefined"
          :seconds="data.deadline"
        />
        <el-button
          v-if="data.status === 'pending'"
          icon="Close"
          size="small"
          @click="handleClose"
        >
          关闭
        </el-button>
      </div>
    </div>

    <!-- 超时提示 -->
    <el-alert
      v-if="isTimeout"
      type="error"
      title="该待办已超时，无法提交"
      :closable="false"
      style="margin-bottom: 16px"
    />

    <!-- 已处理状态显示 -->
    <div v-if="data.status !== 'pending'" class="processed-info">
      <el-descriptions title="处理信息" :column="1" border>
        <el-descriptions-item label="处理状态">
          <el-tag v-if="data.status === 'done'" type="success">已完成</el-tag>
          <el-tag v-else-if="data.status === 'rejected'" type="danger">已驳回</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="处理时间">
          {{ data.submittedAt || '-' }}
        </el-descriptions-item>
        <el-descriptions-item
          v-if="data.formData && Object.keys(data.formData).length > 0"
          label="提交数据"
        >
          <pre class="form-data-display">{{ JSON.stringify(data.formData, null, 2) }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- 动态表单 -->
    <div v-else class="form-section">
      <div class="section-title">请填写以下信息</div>
      <DynamicForm
        ref="formRef"
        :schema="data.formSchema"
        v-model="formData"
      />
    </div>

    <!-- 操作按钮 -->
    <div v-if="canSubmit" class="detail-actions">
      <el-button @click="handleReject" type="danger" plain>
        驳回
      </el-button>
      <el-button type="primary" @click="handleSubmit">
        提交
      </el-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.todo-detail {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.header-left {
  flex: 1;
}

.detail-title {
  margin: 0 0 8px;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.detail-source {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #909399;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.form-section {
  margin: 20px 0;
}

.section-title {
  font-size: 14px;
  font-weight: 500;
  color: #606266;
  margin-bottom: 16px;
}

.processed-info {
  margin: 20px 0;
}

.form-data-display {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  color: #606266;
  margin: 0;
  max-height: 200px;
  overflow: auto;
}

.detail-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}
</style>