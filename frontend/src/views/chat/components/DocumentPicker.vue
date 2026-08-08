<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'

const knowledgeStore = useKnowledgeStore()

const searchKeyword = ref('')
const selectedIds = ref<string[]>([])

const filteredDocs = computed(() => {
  if (!searchKeyword.value) return knowledgeStore.docList
  return knowledgeStore.docList.filter(d => 
    d.name.toLowerCase().includes(searchKeyword.value.toLowerCase())
  )
})

onMounted(() => {
  // 加载文档列表（需要先有知识库）
})

function handleSelect(id: string) {
  const index = selectedIds.value.indexOf(id)
  if (index > -1) {
    selectedIds.value.splice(index, 1)
  } else {
    selectedIds.value.push(id)
  }
}

function handleSelectAll() {
  selectedIds.value = filteredDocs.value.map(d => d.id)
}

function handleClear() {
  selectedIds.value = []
}

function isSelected(id: string) {
  return selectedIds.value.includes(id)
}
</script>

<template>
  <div class="document-picker">
    <div class="picker-header">
      <h4>文档选择</h4>
      <div class="picker-actions">
        <el-button size="small" text @click="handleSelectAll">全选</el-button>
        <el-button size="small" text @click="handleClear">清空</el-button>
      </div>
    </div>
    
    <el-input
      v-model="searchKeyword"
      placeholder="搜索文档"
      prefix-icon="Search"
      clearable
      size="small"
      style="margin: 8px 0"
    />
    
    <el-scrollbar class="picker-list">
      <div class="doc-list">
        <div
          v-for="doc in filteredDocs"
          :key="doc.id"
          class="doc-item"
          :class="{ selected: isSelected(doc.id) }"
          @click="handleSelect(doc.id)"
        >
          <el-checkbox :model-value="isSelected(doc.id)" @click.stop />
          <span class="doc-name">{{ doc.name }}</span>
        </div>
        
        <el-empty v-if="filteredDocs.length === 0" description="暂无文档" :image-size="48" />
      </div>
    </el-scrollbar>
    
    <div class="picker-footer">
      已选 {{ selectedIds.length }} 篇
    </div>
  </div>
</template>

<style lang="scss" scoped>
.document-picker {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
}

.picker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
  
  h4 {
    margin: 0;
    font-size: 14px;
    color: #303133;
  }
}

.picker-list {
  flex: 1;
  min-height: 0;
}

.doc-list {
  padding: 8px;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 4px;
  cursor: pointer;
  margin-bottom: 4px;
  
  &:hover {
    background: #f5f7fa;
  }
  
  &.selected {
    background: #ecf5ff;
    
    .doc-name {
      color: #409eff;
    }
  }
  
  .doc-name {
    flex: 1;
    font-size: 13px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.picker-footer {
  padding: 12px 16px;
  border-top: 1px solid #ebeef5;
  font-size: 12px;
  color: #909399;
}
</style>

