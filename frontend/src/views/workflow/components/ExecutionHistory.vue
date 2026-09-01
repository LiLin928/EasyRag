<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as wfApi from '@/api/workflow'
import type { Execution, ExecutionDetail, NodeExecutionDetail } from '@/types/workflow'

defineProps<{
  data: Execution[]
}>()

const router = useRouter()

// 执行详情弹窗
const detailVisible = ref(false)
const detailLoading = ref(false)
const executionDetail = ref<ExecutionDetail | null>(null)
const activeDetailTab = ref('inputs')
const selectedNodeDetail = ref<NodeExecutionDetail | null>(null)
const nodeDetailVisible = ref(false)

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

async function handleViewDetail(row: Execution) {
  detailVisible.value = true
  detailLoading.value = true
  activeDetailTab.value = 'inputs'
  try {
    executionDetail.value = await wfApi.getExecutionDetail(row.id)
  } catch (error) {
    ElMessage.error('获取执行详情失败')
  } finally {
    detailLoading.value = false
  }
}

function showNodeDetail(node: NodeExecutionDetail) {
  selectedNodeDetail.value = node
  nodeDetailVisible.value = true
}

function getNodeStatusType(status: string) {
  const map: Record<string, any> = {
    success: 'success',
    error: 'danger',
    running: 'primary',
    wait: 'warning'
  }
  return map[status] || 'info'
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
    
    <el-table-column label="操作" width="140" fixed="right">
      <template #default="{ row }">
        <el-button 
          link 
          type="primary" 
          size="small"
          @click="handleViewDetail(row)"
        >
          查看
        </el-button>
        <el-button 
          v-if="row.status === 'error'" 
          link 
          type="primary" 
          size="small"
          @click="handleRerun(row)"
        >
          重跑
        </el-button>
      </template>
    </el-table-column>
  </el-table>

  <!-- 执行详情弹窗 -->
  <el-dialog
    v-model="detailVisible"
    title="执行详情"
    width="900px"
    destroy-on-close
  >
    <div v-if="detailLoading" class="detail-loading">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>加载中...</p>
    </div>
    
    <div v-else-if="executionDetail" class="execution-detail">
      <!-- 基本信息 -->
      <div class="detail-header">
        <div class="detail-info-item">
          <span class="label">流程:</span>
          <span class="value">{{ executionDetail.workflowName }}</span>
        </div>
        <div class="detail-info-item">
          <span class="label">状态:</span>
          <el-tag :type="getStatusType(executionDetail.status)" size="small">
            {{ getStatusLabel(executionDetail.status) }}
          </el-tag>
        </div>
        <div class="detail-info-item">
          <span class="label">触发:</span>
          <span class="value">{{ getTriggerLabel(executionDetail.trigger) }}</span>
        </div>
        <div class="detail-info-item">
          <span class="label">耗时:</span>
          <span class="value">{{ formatDuration(executionDetail.duration) }}</span>
        </div>
      </div>

      <!-- 详情标签页 -->
      <el-tabs v-model="activeDetailTab" class="detail-tabs">
        <el-tab-pane label="输入参数" name="inputs">
          <div class="detail-content">
            <pre v-if="Object.keys(executionDetail.inputs || {}).length > 0">{{ JSON.stringify(executionDetail.inputs, null, 2) }}</pre>
            <el-empty v-else description="无输入参数" :image-size="60" />
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="最终结果" name="outputs">
          <div class="detail-content">
            <pre v-if="Object.keys(executionDetail.outputs || {}).length > 0">{{ JSON.stringify(executionDetail.outputs, null, 2) }}</pre>
            <el-empty v-else description="无输出结果" :image-size="60" />
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="节点执行" name="nodes">
          <div class="detail-content">
            <el-table v-if="executionDetail.nodes?.length > 0" :data="executionDetail.nodes" stripe size="small">
              <el-table-column prop="nodeName" label="节点" min-width="120" />
              <el-table-column prop="nodeType" label="类型" width="100" />
              <el-table-column label="状态" width="80">
                <template #default="{ row: nodeRow }">
                  <el-tag :type="getNodeStatusType(nodeRow.status)" size="small">
                    {{ getStatusLabel(nodeRow.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="耗时" width="80">
                <template #default="{ row: nodeRow }">
                  {{ formatDuration(nodeRow.duration) }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80" fixed="right">
                <template #default="{ row: nodeRow }">
                  <el-button link type="primary" size="small" @click="showNodeDetail(nodeRow)">
                    详情
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="无节点执行记录" :image-size="60" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <template #footer>
      <el-button @click="detailVisible = false">关闭</el-button>
    </template>
  </el-dialog>

  <!-- 节点执行详情弹窗 -->
  <el-dialog
    v-model="nodeDetailVisible"
    :title="`节点执行详情: ${selectedNodeDetail?.nodeName || ''}`"
    width="700px"
    destroy-on-close
    append-to-body
  >
    <div v-if="selectedNodeDetail" class="node-detail">
      <div class="node-detail-item">
        <span class="label">节点ID:</span>
        <span class="value">{{ selectedNodeDetail.nodeId }}</span>
      </div>
      <div class="node-detail-item">
        <span class="label">节点类型:</span>
        <span class="value">{{ selectedNodeDetail.nodeType }}</span>
      </div>
      <div class="node-detail-item">
        <span class="label">状态:</span>
        <el-tag :type="getNodeStatusType(selectedNodeDetail.status)" size="small">
          {{ getStatusLabel(selectedNodeDetail.status) }}
        </el-tag>
      </div>
      <div class="node-detail-item">
        <span class="label">开始时间:</span>
        <span class="value">{{ selectedNodeDetail.startTime }}</span>
      </div>
      <div class="node-detail-item">
        <span class="label">结束时间:</span>
        <span class="value">{{ selectedNodeDetail.endTime || '-' }}</span>
      </div>
      <div class="node-detail-item">
        <span class="label">耗时:</span>
        <span class="value">{{ formatDuration(selectedNodeDetail.duration) }}</span>
      </div>
      
      <el-divider />
      
      <div class="node-detail-section">
        <h4>输入</h4>
        <pre v-if="selectedNodeDetail.input !== undefined">{{ JSON.stringify(selectedNodeDetail.input, null, 2) }}</pre>
        <el-empty v-else description="无输入数据" :image-size="40" />
      </div>
      
      <el-divider />
      
      <div class="node-detail-section">
        <h4>输出</h4>
        <pre v-if="selectedNodeDetail.output !== undefined">{{ JSON.stringify(selectedNodeDetail.output, null, 2) }}</pre>
        <el-empty v-else description="无输出数据" :image-size="40" />
      </div>
      
      <div v-if="selectedNodeDetail.error" class="node-detail-section">
        <el-divider />
        <h4>错误信息</h4>
        <pre class="error-content">{{ selectedNodeDetail.error }}</pre>
      </div>
    </div>
  </el-dialog>
</template>


<style lang="scss" scoped>
.detail-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: #909399;

  p {
    margin-top: 12px;
  }
}

.execution-detail {
  .detail-header {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    margin-bottom: 20px;
    padding: 12px;
    background: #f5f7fa;
    border-radius: 4px;

    .detail-info-item {
      display: flex;
      align-items: center;
      gap: 8px;

      .label {
        color: #606266;
        font-size: 13px;
      }

      .value {
        color: #303133;
        font-size: 13px;
        font-weight: 500;
      }
    }
  }

  .detail-tabs {
    .detail-content {
      min-height: 200px;
      max-height: 400px;
      overflow: auto;

      pre {
        background: #f5f7fa;
        padding: 12px;
        border-radius: 4px;
        font-size: 12px;
        line-height: 1.5;
        white-space: pre-wrap;
        word-break: break-all;
      }
    }
  }
}

.node-detail {
  .node-detail-item {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;

    .label {
      color: #606266;
      font-size: 13px;
      min-width: 80px;
    }

    .value {
      color: #303133;
      font-size: 13px;
    }
  }

  .node-detail-section {
    h4 {
      margin: 0 0 12px 0;
      font-size: 14px;
      color: #303133;
    }

    pre {
      background: #f5f7fa;
      padding: 12px;
      border-radius: 4px;
      font-size: 12px;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-all;
      max-height: 200px;
      overflow: auto;

      &.error-content {
        background: #fef0f0;
        color: #f56c6c;
      }
    }
  }
}
</style>
