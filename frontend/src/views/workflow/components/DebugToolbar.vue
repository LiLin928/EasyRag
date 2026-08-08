<script setup lang="ts">
import { useWorkflowExecutionStore } from '@/stores/workflow'

const store = useWorkflowExecutionStore()

function handleContinue() {
  // TODO: 继续执行
  console.log('Continue execution')
}

function handleStop() {
  // TODO: 停止执行
  console.log('Stop execution')
}

function handleStepOver() {
  // TODO: 单步执行
  console.log('Step over')
}
</script>

<template>
  <div v-if="store.debugMode && store.executing" class="debug-toolbar">
    <div class="toolbar-left">
      <el-icon class="debug-icon"><Cpu /></el-icon>
      <span class="debug-label">调试模式</span>
      <el-tag size="small" type="warning">
        当前节点: {{ store.logs.length }}
      </el-tag>
    </div>
    
    <div class="toolbar-right">
      <el-button type="success" size="small" icon="VideoPlay" @click="handleContinue">
        继续
      </el-button>
      <el-button type="primary" size="small" icon="Right" @click="handleStepOver">
        单步
      </el-button>
      <el-button type="danger" size="small" icon="VideoPause" @click="handleStop">
        停止
      </el-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.debug-toolbar {
  position: absolute;
  top: 70px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 16px;
  background: #fff;
  border: 1px solid #fde047;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: 100;
  
  .toolbar-left {
    display: flex;
    align-items: center;
    gap: 8px;
    
    .debug-icon {
      color: #f59e0b;
      font-size: 18px;
    }
    
    .debug-label {
      font-size: 13px;
      font-weight: 500;
      color: #303133;
    }
  }
  
  .toolbar-right {
    display: flex;
    gap: 8px;
  }
}
</style>
