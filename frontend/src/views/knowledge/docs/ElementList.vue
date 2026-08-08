<script setup lang="ts">
import { watch } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import ElementCard from './ElementCard.vue'
import type { TreeNode } from '@/types/knowledge'

const props = defineProps<{
  docId: string
  selectedNode?: TreeNode | null
}>()

const knowledgeStore = useKnowledgeStore()

// 监听选中节点变化
watch(() => props.selectedNode, (node) => {
  if (node) {
    knowledgeStore.loadElements(props.docId, { nodeId: node.node_id })
  }
}, { immediate: true })
</script>

<template>
  <div class="element-list">
    <div class="list-header">
      <h3>{{ selectedNode?.title || '全部元素' }}</h3>
      <span class="element-count">{{ knowledgeStore.elementTotal }} 个元素</span>
    </div>
    
    <el-scrollbar v-if="knowledgeStore.elements.length > 0">
      <div class="element-grid">
        <ElementCard
          v-for="element in knowledgeStore.elements"
          :key="element.element_id"
          :data="element"
        />
      </div>
    </el-scrollbar>
    
    <div v-else class="empty-elements">
      <el-empty description="暂无元素数据" />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.element-list {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  
  h3 {
    margin: 0;
    font-size: 16px;
    color: #303133;
  }
  
  .element-count {
    font-size: 13px;
    color: #909399;
  }
}

.element-grid {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.empty-elements {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
