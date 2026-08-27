<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from '@vue-flow/core'
import { useWorkflowEditorStore } from '@/stores/workflow'
import { NODE_TYPES } from '@/types/workflow'

const props = defineProps<EdgeProps>()

const editorStore = useWorkflowEditorStore()
const showMenu = ref(false)

// KEY FIX: wrap in computed() so the path is reactive to node position changes
const pathData = computed(() => getBezierPath(props))

function handleInsert(type: string) {
  if (props.id) {
    editorStore.insertNodeBetween(props.id, type)
  }
  showMenu.value = false
}

const basicNodes = NODE_TYPES.filter(n => n.group === 'basic')
const capNodes = NODE_TYPES.filter(n => n.group === 'cap')

// Click-outside handler to close the dropdown menu
function handleDocumentClick() {
  showMenu.value = false
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
})

onUnmounted(() => {
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<template>
  <BaseEdge :path="pathData[0]" />

  <EdgeLabelRenderer>
    <div
      class="edge-plus-wrapper"
      :style="{
        transform: `translate(-50%, -50%) translate(${pathData[1]}px, ${pathData[2]}px)`
      }"
      @click.stop="showMenu = !showMenu"
    >
      <div class="edge-plus-btn">+</div>
    </div>

    <div
      v-if="showMenu"
      class="edge-node-menu"
      :style="{
        transform: `translate(-50%, 0) translate(${pathData[1]}px, ${pathData[2] + 15}px)`
      }"
      @click.stop
    >
      <div class="menu-group">
        <div class="menu-group-title">基础节点</div>
        <div
          v-for="node in basicNodes"
          :key="node.type"
          class="menu-item"
          @click="handleInsert(node.type)"
        >
          <el-icon :size="14"><component :is="node.icon" /></el-icon>
          <span>{{ node.name }}</span>
        </div>
      </div>
      <div class="menu-group">
        <div class="menu-group-title">能力节点</div>
        <div
          v-for="node in capNodes"
          :key="node.type"
          class="menu-item"
          @click="handleInsert(node.type)"
        >
          <el-icon :size="14"><component :is="node.icon" /></el-icon>
          <span>{{ node.name }}</span>
        </div>
      </div>
    </div>
  </EdgeLabelRenderer>
</template>

<style lang="scss" scoped>
.edge-plus-wrapper {
  position: absolute;
  pointer-events: all;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  z-index: 10;
}

.edge-plus-btn {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  font-size: 16px;
  font-weight: bold;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s, transform 0.2s;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.4);
}

.edge-plus-wrapper:hover .edge-plus-btn {
  opacity: 1;
  transform: scale(1.1);
}

.edge-node-menu {
  position: absolute;
  pointer-events: all;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  padding: 8px;
  width: 180px;
  max-height: 320px;
  overflow-y: auto;
  z-index: 1000;
}

.menu-group {
  margin-bottom: 8px;
}

.menu-group-title {
  font-size: 12px;
  color: #909399;
  padding: 4px 0;
  font-weight: 600;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  cursor: pointer;
  border-radius: 4px;
  font-size: 13px;
  transition: background 0.15s;

  &:hover {
    background: #f0f7ff;
    color: #409eff;
  }
}
</style>