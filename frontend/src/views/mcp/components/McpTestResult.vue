<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useMcpStore } from '@/stores/mcp'
import type { Mcp, McpTestResult } from '@/types/mcp'

interface Props {
  visible: boolean
  mcp?: Mcp | null
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  mcp: null
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const mcpStore = useMcpStore()
const loading = ref(false)
const testResult = ref<McpTestResult | null>(null)

// 监听 visible 变化，重置状态
watch(() => props.visible, (val) => {
  if (val && props.mcp) {
    testResult.value = null
    handleTest()
  }
})

function handleClose() {
  emit('update:visible', false)
}

async function handleTest() {
  if (!props.mcp) return

  loading.value = true
  testResult.value = null

  try {
    const result = await mcpStore.testMcp(props.mcp.id)
    testResult.value = result

    if (result.success) {
      ElMessage.success(`测试成功，耗时 ${result.duration}ms`)
    } else {
      ElMessage.error(result.error || '测试失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '测试失败')
    testResult.value = {
      success: false,
      toolCount: 0,
      error: error.message || '未知错误',
      duration: 0
    }
  } finally {
    loading.value = false
  }
}

async function handleRetry() {
  await handleTest()
}
</script>

<template>
  <el-drawer
    :model-value="visible"
    title="MCP 服务测试"
    size="500px"
    @update:model-value="handleClose"
  >
    <div v-if="mcp" class="test-panel">
      <!-- MCP 信息 -->
      <div class="mcp-info">
        <h4>{{ mcp.name }}</h4>
        <div class="mcp-meta">
          <span class="meta-item">
            <el-tag :type="mcp.tp === 'stdio' ? 'primary' : 'warning'" size="small">
              {{ mcp.tp }}
            </el-tag>
          </span>
          <span class="meta-item">
            <code>{{ mcp.cmd }}</code>
          </span>
        </div>
      </div>

      <!-- 测试中状态 -->
      <div v-if="loading && !testResult" class="testing-state">
        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
        <p>正在测试连接...</p>
      </div>

      <!-- 测试结果 -->
      <div v-if="testResult" class="result-section">
        <h4>测试结果</h4>

        <div class="result-meta">
          <el-tag :type="testResult.success ? 'success' : 'danger'" size="small">
            {{ testResult.success ? '连接成功' : '连接失败' }}
          </el-tag>
          <span class="result-duration">耗时: {{ testResult.duration }}ms</span>
        </div>

        <div v-if="testResult.success" class="result-success">
          <div class="result-item">
            <div class="result-label">工具数量:</div>
            <div class="result-value">{{ testResult.toolCount }} 个</div>
          </div>

          <div v-if="testResult.tools && testResult.tools.length > 0" class="result-tools">
            <div class="result-label">可用工具:</div>
            <div class="tools-list">
              <el-tag
                v-for="tool in testResult.tools"
                :key="tool"
                size="small"
                type="info"
                class="tool-tag"
              >
                {{ tool }}
              </el-tag>
            </div>
          </div>
        </div>

        <div v-else class="result-error">
          <div class="result-label">错误信息:</div>
          <el-text type="danger">{{ testResult.error }}</el-text>
        </div>

        <div class="test-actions">
          <el-button
            type="primary"
            icon="Refresh"
            :loading="loading"
            @click="handleRetry"
          >
            重新测试
          </el-button>
        </div>
      </div>
    </div>

    <div v-else class="no-mcp">
      <el-empty description="请选择要测试的 MCP 服务" />
    </div>
  </el-drawer>
</template>

<style lang="scss" scoped>
.test-panel {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.mcp-info {
  h4 {
    margin: 0 0 8px;
    font-size: 16px;
    color: #303133;
  }

  .mcp-meta {
    display: flex;
    align-items: center;
    gap: 12px;

    .meta-item {
      display: flex;
      align-items: center;
      gap: 4px;
    }

    code {
      font-family: 'Courier New', monospace;
      font-size: 12px;
      color: #409eff;
      background: #f5f7fa;
      padding: 4px 8px;
      border-radius: 4px;
    }
  }
}

.testing-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 0;
  color: #909399;

  p {
    margin-top: 12px;
  }
}

.result-section {
  h4 {
    margin: 0 0 12px;
    font-size: 14px;
    color: #303133;
  }

  .result-meta {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;

    .result-duration {
      font-size: 12px;
      color: #909399;
    }
  }

  .result-success {
    border: 1px solid #e4e7ed;
    border-radius: 4px;
    padding: 12px;
    background: #fafafa;

    .result-item {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;

      .result-label {
        font-size: 12px;
        color: #909399;
        min-width: 80px;
      }

      .result-value {
        font-size: 14px;
        color: #303133;
        font-weight: 500;
      }
    }

    .result-tools {
      .result-label {
        font-size: 12px;
        color: #909399;
        margin-bottom: 8px;
      }

      .tools-list {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .tool-tag {
        font-family: 'Courier New', monospace;
      }
    }
  }

  .result-error {
    border: 1px solid #fde2e2;
    border-radius: 4px;
    padding: 12px;
    background: #fef2f2;

    .result-label {
      font-size: 12px;
      color: #dc2626;
      margin-bottom: 8px;
      font-weight: 500;
    }
  }

  .test-actions {
    margin-top: 16px;
    display: flex;
    gap: 8px;
  }
}

.no-mcp {
  padding: 48px 0;
}
</style>
