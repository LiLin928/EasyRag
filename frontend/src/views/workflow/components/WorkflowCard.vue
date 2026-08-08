<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useWorkflowListStore } from '@/stores/workflow'
import type { Workflow } from '@/types/workflow'

const props = defineProps<{
  data: Workflow
}>()

const router = useRouter()
const store = useWorkflowListStore()

function handleClick() {
  router.push('/workflows/editor/' + props.data.id)
}

async function handleDuplicate(e: Event) {
  e.stopPropagation()
  try {
    const wf = await store.duplicateWorkflow(props.data.id)
    ElMessage.success('复制成功')
    router.push('/workflows/editor/' + wf.id)
  } catch (error) {
    // 取消
  }
}

async function handleDelete(e: Event) {
  e.stopPropagation()
  try {
    await ElMessageBox.confirm('确定要删除流程"' + props.data.name + '"吗？', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await store.deleteWorkflow(props.data.id)
    ElMessage.success('删除成功')
  } catch (error) {
    // 取消删除
  }
}

function getStatusType(status: string) {
  return status === 'published' ? 'success' : 'info'
}

function getStatusLabel(status: string) {
  return status === 'published' ? '已发布' : '草稿'
}
</script>

<template>
  <div class="workflow-card" @click="handleClick">
    <div class="card-header">
      <el-icon class="card-icon" :size="32">
        <component :is="data.icon || 'Document'" />
      </el-icon>
      <el-tag :type="getStatusType(data.status)" size="small">
        {{ getStatusLabel(data.status) }}
      </el-tag>
    </div>
    
    <h3 class="card-title">{{ data.name }}</h3>
    <p class="card-desc">{{ data.description || '暂无描述' }}</p>
    
    <div class="card-meta">
      <span>v{{ data.version }}</span>
      <span v-if="data.successRate">{{ data.successRate }}%</span>
      <span v-if="data.lastRun">{{ data.lastRun.split(' ')[0] }}</span>
    </div>
    
    <div class="card-actions">
      <el-button link type="primary" size="small" @click="handleDuplicate">
        复制
      </el-button>
      <el-button link type="danger" size="small" @click="handleDelete">
        删除
      </el-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.workflow-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #ebeef5;
  
  &:hover {
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    border-color: #409eff;
    
    .card-actions {
      opacity: 1;
    }
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.card-icon {
  color: #409eff;
}

.card-title {
  margin: 0 0 8px;
  font-size: 16px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-desc {
  margin: 0 0 12px;
  font-size: 13px;
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #c0c4cc;
  margin-bottom: 8px;
}

.card-actions {
  display: flex;
  gap: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}
</style>
