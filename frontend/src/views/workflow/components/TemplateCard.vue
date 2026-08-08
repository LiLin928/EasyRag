<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { useWorkflowListStore } from '@/stores/workflow'
import type { Template } from '@/types/workflow'

const props = defineProps<{
  data: Template
}>()

const store = useWorkflowListStore()

async function handleUse() {
  try {
    await store.createFromTemplate(props.data.id, props.data.name)
    ElMessage.success('创建成功')
    // TODO: 跳转到编辑器
  } catch (error) {
    ElMessage.error('创建失败')
  }
}

function getSourceType(source: string) {
  return source === 'official' ? 'success' : 'warning'
}

function getSourceLabel(source: string) {
  return source === 'official' ? '官方' : '社区'
}
</script>

<template>
  <div class="template-card">
    <div class="card-header">
      <el-tag :type="getSourceType(data.source)" size="small">
        {{ getSourceLabel(data.source) }}
      </el-tag>
    </div>
    
    <h3 class="card-title">{{ data.name }}</h3>
    <p class="card-desc">{{ data.description || '暂无描述' }}</p>
    
    <div class="card-tags">
      <el-tag v-for="tag in data.tags" :key="tag" size="small" effect="plain">
        {{ tag }}
      </el-tag>
    </div>
    
    <div class="card-meta">
      <span>{{ data.nodeCount }} 个节点</span>
      <span>{{ data.useCount }} 次使用</span>
    </div>
    
    <el-button type="primary" size="small" class="use-btn" @click="handleUse">
      使用此模板
    </el-button>
  </div>
</template>

<style lang="scss" scoped>
.template-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #ebeef5;
  transition: all 0.2s;
  
  &:hover {
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  }
}

.card-header {
  margin-bottom: 12px;
}

.card-title {
  margin: 0 0 8px;
  font-size: 16px;
  color: #303133;
}

.card-desc {
  margin: 0 0 12px;
  font-size: 13px;
  color: #909399;
  line-height: 1.5;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 12px;
}

.card-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #c0c4cc;
  margin-bottom: 12px;
}

.use-btn {
  width: 100%;
}
</style>

