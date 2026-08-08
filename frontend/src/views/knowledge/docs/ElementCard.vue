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

function parseTableContent(content: string) {
  try {
    return JSON.parse(content)
  } catch {
    return null
  }
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
        <template v-if="parseTableContent(data.content)">
          <el-table
            :data="parseTableContent(data.content).rows"
            size="small"
            border
          >
            <el-table-column
              v-for="(header, index) in parseTableContent(data.content).headers"
              :key="index"
              :prop="'col' + index"
              :label="header"
            >
              <template #default="{ row }">
                {{ row[index] }}
              </template>
            </el-table-column>
          </el-table>
        </template>
        <span v-else>表格数据解析失败</span>
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
