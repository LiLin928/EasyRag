<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useWorkflowExecutionStore } from '@/stores/workflow'

const store = useWorkflowExecutionStore()

const collapsed = ref(false)
const selectedNodeId = ref('')
const showResultModal = ref(false)
const panelHeight = ref(200)
const isResizing = ref(false)
const minHeight = 100
const maxHeight = 500

const logCount = computed(() => store.logs.length)

const logLevelColor: Record<string, string> = {
  info: '#409eff',
  success: '#16A34A',
  warning: '#D97706',
  error: '#DC2626',
  result: '#9D174D'
}

function handleClear() {
  store.logs = []
}

function handleToggle() {
  collapsed.value = !collapsed.value
}

function getLogColor(level: string) {
  return logLevelColor[level] || '#909399'
}

function formatTime(time: string) {
  return time.split('T')[1]?.substring(0, 8) || time
}

function showNodeResult(nodeId: string) {
  selectedNodeId.value = nodeId
  showResultModal.value = true
}

function getNodeName(nodeId: string) {
  const log = store.logs.find(l => l.nodeId === nodeId && l.content.includes('开始执行'))
  if (log) {
    const match = log.content.match(/开始执行节点: (.+)/)
    return match ? match[1] : nodeId
  }
  return nodeId
}

const selectedNodeResult = computed(() => {
  if (!selectedNodeId.value) return null
  const state = store.nodeStates[selectedNodeId.value]
  return state?.output || '暂无执行结果'
})

// 拖拽调整高度
function startResize(e: MouseEvent) {
  isResizing.value = true
  document.body.style.cursor = 'ns-resize'
  document.body.style.userSelect = 'none'
}

function stopResize() {
  isResizing.value = false
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

function onResize(e: MouseEvent) {
  if (!isResizing.value) return
  const newHeight = window.innerHeight - e.clientY - 56 // 减去顶部栏高度
  panelHeight.value = Math.max(minHeight, Math.min(maxHeight, newHeight))
}

onMounted(() => {
  document.addEventListener('mousemove', onResize)
  document.addEventListener('mouseup', stopResize)
})

onUnmounted(() => {
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', stopResize)
})
</script>

<template>
  <div class="execution-panel" :class="{ collapsed }" :style="{ height: collapsed ? 'auto' : panelHeight + 'px' }">
    <!-- 拖拽调整条 -->
    <div v-if="!collapsed" class="resize-handle" @mousedown="startResize">
      <div class="resize-indicator"></div>
    </div>
    
    <div class="panel-header" @click="handleToggle">
      <div class="header-left">
        <el-icon :class="{ 'rotate': collapsed }"><ArrowDown /></el-icon>
        <span>执行日志</span>
        <el-badge :value="logCount" type="primary" />
      </div>
      <div class="header-right">
        <el-button v-if="!collapsed" link type="danger" size="small" @click.stop="handleClear">
          清空
        </el-button>
      </div>
    </div>
    
    <div v-if="!collapsed" class="panel-content">
      <div v-if="store.logs.length === 0" class="empty-log">
        <el-empty description="暂无执行日志" :image-size="60" />
      </div>
      <div v-else class="log-list">
        <div
          v-for="(log, i) in store.logs"
          :key="i"
          class="log-item"
          :class="{ 'result-log': log.level === 'result' }"
        >
          <span class="log-time">{{ formatTime(log.time) }}</span>
          <span class="log-node" v-if="log.nodeId" @click.stop="log.level === 'result' ? showNodeResult(log.nodeId) : null">{{ log.nodeId }}</span>
          <span class="log-level" :style="{ color: getLogColor(log.level) }">
            [{{ log.level }}]
          </span>
          <span class="log-content" :class="{ 'result-content': log.level === 'result' }">{{ log.content }}</span>
          <el-button
            v-if="log.level === 'result'"
            link
            type="primary"
            size="small"
            @click.stop="showNodeResult(log.nodeId)"
          >
            查看详情
          </el-button>
        </div>
      </div>
    </div>

    <!-- 节点执行结果弹窗 -->
    <el-dialog
      v-model="showResultModal"
      :title="`节点执行结果: ${getNodeName(selectedNodeId)}`"
      width="700px"
      destroy-on-close
    >
      <div class="result-content">
        <pre v-if="selectedNodeResult">{{ selectedNodeResult }}</pre>
        <el-empty v-else description="暂无执行结果" />
      </div>
      <template #footer>
        <el-button @click="showResultModal = false">关闭</el-button>
        <el-button type="primary" @click="showResultModal = false">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.execution-panel {
  background: #fff;
  border-top: 1px solid #ebeef5;
  transition: all 0.3s;
  display: flex;
  flex-direction: column;
  
  &.collapsed {
    height: auto !important;
    
    .panel-header {
      .el-icon {
        transform: rotate(-90deg);
      }
    }
  }
}

.resize-handle {
  height: 6px;
  background: transparent;
  cursor: ns-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
  
  &:hover {
    background: #e4e7ed;
    
    .resize-indicator {
      opacity: 1;
    }
  }
}

.resize-indicator {
  width: 40px;
  height: 3px;
  background: #c0c4cc;
  border-radius: 2px;
  opacity: 0.5;
  transition: opacity 0.2s;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: #fafafa;
  cursor: pointer;
  user-select: none;
  flex-shrink: 0;
  
  &:hover {
    background: #f5f7fa;
  }
  
  .header-left {
    display: flex;
    align-items: center;
    gap: 8px;
    
    .el-icon {
      transition: transform 0.3s;
      
      &.rotate {
        transform: rotate(-90deg);
      }
    }
    
    span {
      font-size: 14px;
      font-weight: 500;
      color: #303133;
    }
  }
}

.panel-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.empty-log {
  padding: 20px;
  flex: 1;
}

.log-list {
  padding: 8px 16px;
  overflow-y: auto;
  flex: 1;
}

.log-item {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
  font-family: 'Consolas', monospace;
  align-items: flex-start;
  line-height: 1.5;
  
  &.result-log {
    background: #fdf4ff;
    border-radius: 4px;
    padding: 6px 8px;
    margin: 2px 0;
  }
  
  .log-time {
    color: #909399;
    min-width: 60px;
    flex-shrink: 0;
  }
  
  .log-node {
    color: #409eff;
    min-width: 80px;
    cursor: pointer;
    flex-shrink: 0;
    
    &:hover {
      text-decoration: underline;
    }
  }
  
  .log-level {
    min-width: 50px;
    font-weight: 500;
    flex-shrink: 0;
  }
  
  .log-content {
    color: #606266;
    flex: 1;
    word-break: break-all;
    
    &.result-content {
      color: #9D174D;
      font-weight: 500;
    }
  }
  
  .el-button {
    flex-shrink: 0;
    padding: 0 4px;
    height: 18px;
    font-size: 11px;
  }
}

.result-content {
  max-height: 500px;
  overflow: auto;
  
  pre {
    background: #f5f7fa;
    padding: 12px;
    border-radius: 4px;
    font-size: 12px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-all;
    margin: 0;
  }
}
</style>
