<script setup lang="ts">
import type { DocElement } from '@/types/knowledge'

interface Props {
  data: DocElement
}

defineProps<Props>()

const typeMap: Record<string, { label: string; color: string }> = {
  text: { label: '文本', color: '#409eff' },
  table: { label: '表格', color: '#67c23a' },
  image: { label: '图片', color: '#e6a23c' },
  heading: { label: '标题', color: '#909399' }
}

function getTypeInfo(type: string) {
  return typeMap[type] || { label: type, color: '#909399' }
}
</script>

<template>
  <div class="element-card">
    <div class="element-header">
      <el-tag size="small" :style="{ backgroundColor: getTypeInfo(data.type).color, color: '#fff', border: 'none' }">
        {{ getTypeInfo(data.type).label }}
      </el-tag>
      <span class="element-page">P{{ data.page_number }}</span>
    </div>
    
    <div class="element-content">
      <!-- 文本类型 -->
      <div v-if="data.type === 'text'" class="content-text">
        {{ data.content }}
      </div>
      
      <!-- 标题类型 -->
      <div v-else-if="data.type === 'heading'" class="content-heading">
        {{ data.content }}
      </div>
      
      <!-- 表格类型 -->
      <div v-else-if="data.type === 'table'" class="content-table">
        <!-- 优先使用 HTML 格式渲染 -->
        <div
          v-if="data.metadata?.html"
          class="table-html"
          v-html="data.metadata.html"
        ></div>
        <!-- 回退到纯文本显示 -->
        <pre v-else class="table-text">{{ data.content }}</pre>
      </div>
      
      <!-- 图片类型 -->
      <div v-else-if="data.type === 'image'" class="content-image">
        <el-image :src="data.content" fit="contain" />
      </div>
      
      <!-- 其他类型 -->
      <div v-else class="content-other">
        {{ data.content }}
      </div>
    </div>
    
    <div class="element-footer">
      <span class="node-title">{{ data.node_title }}</span>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.element-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #ebeef5;
}

.element-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  
  .element-page {
    font-size: 12px;
    color: #909399;
  }
}

.element-content {
  .content-text {
    font-size: 14px;
    color: #606266;
    line-height: 1.6;
    white-space: pre-wrap;
  }
  
  .content-heading {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
  }
  
  .content-table {
    overflow-x: auto;

    .table-html {
      :deep(table) {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;

        th, td {
          padding: 8px 12px;
          border: 1px solid #dcdfe6;
          text-align: left;
        }

        th {
          background: #f5f7fa;
          font-weight: 600;
          color: #303133;
        }

        td {
          color: #606266;
        }

        tr:hover {
          background: #f5f7fa;
        }
      }
    }

    .table-text {
      margin: 0;
      padding: 12px;
      background: #f5f7fa;
      border-radius: 4px;
      font-size: 12px;
      color: #606266;
      white-space: pre-wrap;
      word-break: break-word;
    }
  }
  
  .content-image {
    text-align: center;
    
    :deep(.el-image) {
      max-width: 100%;
      max-height: 300px;
    }
  }
}

.element-footer {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
  
  .node-title {
    font-size: 12px;
    color: #909399;
  }
}
</style>
