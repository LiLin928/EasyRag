<script setup lang="ts">
import { ref, computed } from 'vue'
import { useWorkflowExecutionStore } from '@/stores/workflow'

const store = useWorkflowExecutionStore()

const collapsed = ref(false)

const logCount = computed(() => store.logs.length)

const logLevelColor: Record<string, string> = {
  info: '#409eff',
  success: '#16A34A',
  warning: '#D97706',
  error: '#DC2626'
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
</script>

<template>
  <div class="execution-panel" :class="{ collapsed }">
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
        >
          <span class="log-time">{{ formatTime(log.time) }}</span>
          <span class="log-node" v-if="log.nodeId">{{ log.nodeId }}</span>
          <span class="log-level" :style="{ color: getLogColor(log.level) }">
            [{{ log.level }}]
          </span>
          <span class="log-content">{{ log.content }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.execution-panel {
  background: #fff;
  border-top: 1px solid #ebeef5;
  transition: all 0.3s;
  
  &.collapsed {
    .panel-header {
      .el-icon {
        transform: rotate(-90deg);
      }
    }
  }
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #fafafa;
  cursor: pointer;
  user-select: none;
  
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
  max-height: 200px;
  overflow-y: auto;
}

.empty-log {
  padding: 20px;
}

.log-list {
  padding: 8px 16px;
}

.log-item {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
  font-family: 'Consolas', monospace;
  
  .log-time {
    color: #909399;
    min-width: 60px;
  }
  
  .log-node {
    color: #409eff;
    min-width: 80px;
  }
  
  .log-level {
    min-width: 50px;
    font-weight: 500;
  }
  
  .log-content {
    color: #606266;
    flex: 1;
  }
}
</style>
