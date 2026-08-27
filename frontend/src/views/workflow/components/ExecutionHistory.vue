<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as wfApi from '@/api/workflow'
import type { Execution } from '@/types/workflow'

defineProps<{
  data: Execution[]
}>()

const router = useRouter()

function getStatusType(status: string) {
  const map: Record<string, any> = {
    success: 'success',
    error: 'danger',
    running: 'primary',
    wait: 'warning',
    cancelled: 'info'
  }
  return map[status] || 'info'
}

function getStatusLabel(status: string) {
  const map: Record<string, string> = {
    success: '成功',
    error: '失败',
    running: '运行中',
    wait: '等待中',
    cancelled: '已取消'
  }
  return map[status] || status
}

function getTriggerLabel(trigger: string) {
  const map: Record<string, string> = {
    manual: '手动触发',
    schedule: '定时触发',
    api: 'API 触发',
    agent: '智能体触发'
  }
  return map[trigger] || trigger
}

function formatDuration(ms?: number) {
  if (!ms) return '-'
  if (ms < 1000) return ms + 'ms'
  return (ms / 1000).toFixed(1) + 's'
}

async function handleRerun(row: Execution) {
  try {
    await wfApi.executeWorkflow(row.workflowId)
    ElMessage.success('已触发重跑')
    router.push('/workflows/editor/' + row.workflowId)
  } catch (error) {
    ElMessage.error('重跑失败')
  }
}
</script>


<template>
  <el-table :data="data" stripe>
    <el-table-column prop="workflowName" label="流程" min-width="160" />
    
    <el-table-column label="状态" width="100">
      <template #default="{ row }">
        <el-tag :type="getStatusType(row.status)" size="small">
          {{ getStatusLabel(row.status) }}
        </el-tag>
      </template>
    </el-table-column>
    
    <el-table-column label="触发方式" width="100">
      <template #default="{ row }">
        {{ getTriggerLabel(row.trigger) }}
      </template>
    </el-table-column>
    
    <el-table-column prop="startTime" label="开始时间" width="160" />
    
    <el-table-column label="耗时" width="80">
      <template #default="{ row }">
        {{ formatDuration(row.duration) }}
      </template>
    </el-table-column>
    
    <el-table-column label="节点进度" width="80">
      <template #default="{ row }">
        {{ row.nodeProgress }}
      </template>
    </el-table-column>
    
    <el-table-column label="操作" width="80" fixed="right">
      <template #default="{ row }">
        <el-button 
          v-if="row.status === 'error'" 
          link 
          type="primary" 
          size="small"
          @click="handleRerun(row as Execution)"
        >
          重跑
        </el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

