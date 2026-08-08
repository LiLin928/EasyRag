<script setup lang="ts">
import { ref, watch } from 'vue'
import type { TreeNode } from '@/types/knowledge'

interface Props {
  data: TreeNode[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  select: [node: TreeNode]
}>()

const expandedKeys = ref<string[]>([])
const selectedKey = ref<string>('')

// 默认展开第一级
watch(() => props.data, (data) => {
  if (data.length > 0) {
    expandedKeys.value = data.map(n => n.node_id)
  }
}, { immediate: true })

function handleNodeClick(nodeData: TreeNode) {
  selectedKey.value = nodeData.node_id
  emit('select', nodeData)
}
</script>

<template>
  <div class="tree-browser">
    <el-tree
      :data="data"
      :props="{
        children: 'children',
        label: 'title'
      }"
      node-key="node_id"
      :default-expanded-keys="expandedKeys"
      :highlight-current="true"
      @node-click="handleNodeClick"
    >
      <template #default="{ data }">
        <div class="tree-node" :class="{ active: selectedKey === data.node_id }">
          <span class="node-title">{{ data.title }}</span>
          <el-badge :value="data.element_count" :max="99" class="node-count" />
        </div>
      </template>
    </el-tree>
  </div>
</template>

<style lang="scss" scoped>
.tree-browser {
  height: 100%;
  overflow: auto;
  
  :deep(.el-tree) {
    background: transparent;
    
    .el-tree-node__content {
      height: auto;
      padding: 8px 0;
    }
    
    .el-tree-node.is-current > .el-tree-node__content {
      background: #ecf5ff;
    }
  }
}

.tree-node {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 8px;
  
  .node-title {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .node-count {
    margin-left: 8px;
    
    :deep(.el-badge__content) {
      font-size: 10px;
      height: 16px;
      line-height: 16px;
    }
  }
}
</style>
