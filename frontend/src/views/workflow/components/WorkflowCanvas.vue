<script setup lang="ts">
import { ref, watch, markRaw } from 'vue'
import { VueFlow, useVueFlow, type Node, type Edge } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { useWorkflowEditorStore, useWorkflowExecutionStore } from '@/stores/workflow'
import BaseNodeCard from './BaseNodeCard.vue'
import AddButtonEdge from './AddButtonEdge.vue'
import type { WfEdge } from '@/types/workflow'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'

const editorStore = useWorkflowEditorStore()
const edgeTypes = {
  default: markRaw(AddButtonEdge)
}
const execStore = useWorkflowExecutionStore()
const { onConnect, onNodeDragStop, onNodeDoubleClick, onNodesChange } = useVueFlow()

const nodes = ref<Node[]>([])
const edges = ref<Edge[]>([])

watch(
  () => editorStore.nodes,
  (storeNodes) => {
    nodes.value = storeNodes.map(n => ({
      id: n.id,
      type: n.type,
      position: n.position,
      data: {
        ...n.data,
        name: n.name
      }
    }))
  },
  { immediate: true, deep: true }
)

watch(
  () => editorStore.edges,
  (storeEdges) => {
    edges.value = storeEdges.map(e => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.label,
      sourceHandle: e.sourceHandle
    }))
  },
  { immediate: true, deep: true }
)

onConnect((params) => {
  const newEdge: WfEdge = {
    id: 'e-' + Date.now(),
    source: params.source,
    target: params.target,
    sourceHandle: params.sourceHandle as 'yes' | 'no' | undefined
  }
  editorStore.addEdge(newEdge)
})

onNodeDragStop((event) => {
  const node = event.node
  editorStore.updateNode(node.id, {
    position: { x: node.position.x, y: node.position.y }
  })
})

onNodeDoubleClick((event) => {
  const node = event.node
  editorStore.selectedNodeId = node.id
})

onNodesChange((changes) => {
  changes.forEach(change => {
    if (change.type === 'remove') {
      editorStore.removeNode(change.id)
    }
  })
})

function handleDrop(event: DragEvent) {
  const nodeType = event.dataTransfer?.getData('nodeType')
  if (!nodeType) return
  
  const bounds = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const position = {
    x: event.clientX - bounds.left,
    y: event.clientY - bounds.top
  }
  
  editorStore.addNode(nodeType, position)
}

function handleDragOver(event: DragEvent) {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

function getExecStatus(nodeId: string) {
  return execStore.nodeStates[nodeId]?.status || 'idle'
}

function getExecDuration(nodeId: string) {
  return execStore.nodeStates[nodeId]?.durationMs
}
</script>

<template>
  <div class="workflow-canvas" @drop="handleDrop" @dragover="handleDragOver">
    <VueFlow
      v-model:nodes="nodes"
      v-model:edges="edges"
      :default-zoom="1"
      :min-zoom="0.2"
      :max-zoom="4"
      :delete-key-code="['Backspace', 'Delete']"
      :edge-types="edgeTypes"
      fit-view-on-init
      class="vue-flow-canvas"
    >
      <Background pattern-gap="20" :size="1" />
      <Controls />
      <MiniMap />
      
      <template #node-start="nodeProps">
        <BaseNodeCard :node="nodeProps" :exec-status="getExecStatus(nodeProps.id)" :exec-duration="getExecDuration(nodeProps.id)" />
      </template>
      <template #node-end="nodeProps">
        <BaseNodeCard :node="nodeProps" :exec-status="getExecStatus(nodeProps.id)" :exec-duration="getExecDuration(nodeProps.id)" />
      </template>
      <template #node-condition="nodeProps">
        <BaseNodeCard :node="nodeProps" :exec-status="getExecStatus(nodeProps.id)" :exec-duration="getExecDuration(nodeProps.id)" />
      </template>
      <template #node-loop="nodeProps">
        <BaseNodeCard :node="nodeProps" :exec-status="getExecStatus(nodeProps.id)" :exec-duration="getExecDuration(nodeProps.id)" />
      </template>
      <template #node-loop_end="nodeProps">
        <BaseNodeCard :node="nodeProps" :exec-status="getExecStatus(nodeProps.id)" :exec-duration="getExecDuration(nodeProps.id)" />
      </template>
      <template #node-human="nodeProps">
        <BaseNodeCard :node="nodeProps" :exec-status="getExecStatus(nodeProps.id)" :exec-duration="getExecDuration(nodeProps.id)" />
      </template>
      <template #node-variable_assign="nodeProps">
        <BaseNodeCard :node="nodeProps" :exec-status="getExecStatus(nodeProps.id)" :exec-duration="getExecDuration(nodeProps.id)" />
      </template>
      <template #node-template_render="nodeProps">
        <BaseNodeCard :node="nodeProps" :exec-status="getExecStatus(nodeProps.id)" :exec-duration="getExecDuration(nodeProps.id)" />
      </template>
      <template #node-llm="nodeProps">
        <BaseNodeCard :node="nodeProps" :exec-status="getExecStatus(nodeProps.id)" :exec-duration="getExecDuration(nodeProps.id)" />
      </template>
      <template #node-rag="nodeProps">
        <BaseNodeCard :node="nodeProps" :exec-status="getExecStatus(nodeProps.id)" :exec-duration="getExecDuration(nodeProps.id)" />
      </template>
      <template #node-code="nodeProps">
        <BaseNodeCard :node="nodeProps" :exec-status="getExecStatus(nodeProps.id)" :exec-duration="getExecDuration(nodeProps.id)" />
      </template>
      <template #node-http="nodeProps">
        <BaseNodeCard :node="nodeProps" :exec-status="getExecStatus(nodeProps.id)" :exec-duration="getExecDuration(nodeProps.id)" />
      </template>
      <template #node-tool="nodeProps">
        <BaseNodeCard :node="nodeProps" :exec-status="getExecStatus(nodeProps.id)" :exec-duration="getExecDuration(nodeProps.id)" />
      </template>
    </VueFlow>
  </div>
</template>

<style lang="scss" scoped>
.workflow-canvas {
  width: 100%;
  height: 100%;
}

.vue-flow-canvas {
  background: #fafafa;
}

:deep(.vue-flow__node) {
  padding: 0;
  border: none;
  background: transparent;
}

:deep(.vue-flow__edge-path) {
  stroke: #91d5ff;
  stroke-width: 2;
}

:deep(.vue-flow__edge.selected .vue-flow__edge-path) {
  stroke: #409eff;
  stroke-width: 3;
}
</style>

