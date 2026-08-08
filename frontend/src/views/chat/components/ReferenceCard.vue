<script setup lang="ts">
import { ref } from 'vue'
import type { Reference } from '@/types/chat'

interface Props {
  data: Reference
  index: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  expand: [elementId: string]
}>()

const expanded = ref(false)

const typeMap: Record<string, { label: string; color: string }> = {
  text: { label: '文本', color: '#409eff' },
  table: { label: '表格', color: '#67c23a' },
  image: { label: '图片', color: '#e6a23c' }
}

function getTypeInfo(type: string) {
  return typeMap[type] || { label: type, color: '#909399' }
}

function handleExpand() {
  expanded.value = !expanded.value
  if (expanded.value) {
    emit('expand', props.data.element_id)
  }
}
</script>

<template>
  <div class="reference-card" :class="{ expanded }">
    <div class="ref-header" @click="handleExpand">
      <span class="ref-index">[{{ index + 1 }}]</span>
      <span class="ref-title">{{ data.doc_title }}</span>
      <el-tag size="small" :style="{ backgroundColor: getTypeInfo(data.type).color, color: '#fff', border: 'none' }">
        {{ getTypeInfo(data.type).label }}
      </el-tag>
      <span class="ref-score">{{ (data.score * 100).toFixed(0) }}%</span>
      <el-icon class="expand-icon">
        <component :is="expanded ? 'ArrowUp' : 'ArrowDown'" />
      </el-icon>
    </div>
    
    <div v-if="expanded" class="ref-content">
      <div class="ref-node">
        <el-icon><FolderOpened /></el-icon>
        {{ data.node_title }}
      </div>
      <div class="ref-preview">{{ data.content_preview }}</div>
      <div class="ref-actions">
        <el-button size="small" text type="primary">
          <el-icon><View /></el-icon>
          查看详情
        </el-button>
        <el-button size="small" text type="primary">
          <el-icon><Connection /></el-icon>
          查看上下文
        </el-button>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.reference-card {
  background: #f5f7fa;
  border-radius: 6px;
  margin-top: 8px;
  border: 1px solid #ebeef5;
  
  &.expanded {
    background: #fff;
  }
}

.ref-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  
  &:hover {
    background: #f0f0f0;
  }
  
  .ref-index {
    font-weight: 600;
    color: #409eff;
    font-size: 12px;
  }
  
  .ref-title {
    flex: 1;
    font-size: 13px;
    color: #303133;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .ref-score {
    font-size: 12px;
    color: #909399;
  }
  
  .expand-icon {
    color: #909399;
    font-size: 12px;
  }
}

.ref-content {
  padding: 12px;
  border-top: 1px solid #ebeef5;
  
  .ref-node {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: #909399;
    margin-bottom: 8px;
  }
  
  .ref-preview {
    font-size: 13px;
    color: #606266;
    line-height: 1.6;
    margin-bottom: 12px;
  }
  
  .ref-actions {
    display: flex;
    gap: 8px;
  }
}
</style>
