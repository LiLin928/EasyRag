<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useToolStore } from '@/stores/tool'
import type { Tool, ToolTestArgs, ToolTestResult } from '@/types/tool'

interface Props {
  visible: boolean
  tool?: Tool | null
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  tool: null
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const toolStore = useToolStore()
const loading = ref(false)
const testResult = ref<ToolTestResult | null>(null)
const testArgs = reactive<ToolTestArgs>({})

// 监听 visible 变化，重置状态
watch(() => props.visible, (val) => {
  if (val && props.tool) {
    // 重置测试参数
    Object.keys(testArgs).forEach(key => delete testArgs[key])
    props.tool.params.forEach(param => {
      if (param.d) {
        testArgs[param.n] = parseDefaultValue(param.d, param.t)
      }
    })
    testResult.value = null
  }
})

// 解析默认值
function parseDefaultValue(value: string, type: string): any {
  switch (type) {
    case 'boolean':
      return value === 'true'
    case 'number':
      return Number(value)
    case 'object':
    case 'array':
      try {
        return JSON.parse(value)
      } catch {
        return value
      }
    default:
      return value
  }
}

// 格式化显示值
function formatValue(value: unknown): string {
  if (typeof value === 'object') {
    return JSON.stringify(value, null, 2)
  }
  return String(value)
}

function handleClose() {
  emit('update:visible', false)
}

async function handleTest() {
  if (!props.tool) return

  loading.value = true
  testResult.value = null

  try {
    const result = await toolStore.testTool(props.tool.id, testArgs)
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
      error: error.message || '未知错误',
      duration: 0
    }
  } finally {
    loading.value = false
  }
}

const hasArgs = computed(() => {
  return props.tool && props.tool.params.length > 0
})
</script>

<template>
  <el-drawer
    :model-value="visible"
    title="测试工具"
    size="500px"
    @update:model-value="handleClose"
  >
    <div v-if="tool" class="test-panel">
      <!-- 工具信息 -->
      <div class="tool-info">
        <h4>{{ tool.name }}</h4>
        <p class="tool-desc">{{ tool.desc }}</p>
        <div class="tool-sig">
          <code>{{ tool.sig }}</code>
        </div>
      </div>

      <!-- 参数输入 -->
      <div v-if="hasArgs" class="params-section">
        <h4>测试参数</h4>
        <div class="param-inputs">
          <div
            v-for="param in tool.params"
            :key="param.n"
            class="param-input-row"
          >
            <label class="param-label">
              {{ param.n }}
              <span class="param-type">({{ param.t }})</span>
            </label>

            <el-input
              v-if="param.t === 'string'"
              v-model="testArgs[param.n]"
              :placeholder="`默认值: ${param.d}`"
            />

            <el-input-number
              v-else-if="param.t === 'number'"
              v-model="testArgs[param.n]"
              :placeholder="`默认值: ${param.d}`"
              style="width: 100%"
            />

            <el-switch
              v-else-if="param.t === 'boolean'"
              v-model="testArgs[param.n]"
            />

            <el-input
              v-else
              v-model="testArgs[param.n]"
              type="textarea"
              :rows="2"
              :placeholder="`默认值: ${param.d} (JSON格式)`"
            />
          </div>
        </div>
      </div>

      <div v-else class="no-args">
        <el-text type="info">该工具无需参数</el-text>
      </div>

      <!-- 执行按钮 -->
      <div class="test-actions">
        <el-button
          type="primary"
          icon="Connection"
          :loading="loading"
          @click="handleTest"
        >
          执行测试
        </el-button>
      </div>

      <!-- 结果展示 -->
      <div v-if="testResult" class="result-section">
        <h4>执行结果</h4>

        <div class="result-meta">
          <el-tag :type="testResult.success ? 'success' : 'danger'" size="small">
            {{ testResult.success ? '成功' : '失败' }}
          </el-tag>
          <span class="result-duration">耗时: {{ testResult.duration }}ms</span>
        </div>

        <div v-if="testResult.success" class="result-data">
          <div class="result-label">返回数据:</div>
          <pre class="result-json">{{ formatValue(testResult.data) }}</pre>
        </div>

        <div v-else class="result-error">
          <div class="result-label">错误信息:</div>
          <el-text type="danger">{{ testResult.error }}</el-text>
        </div>
      </div>
    </div>

    <div v-else class="no-tool">
      <el-empty description="请选择要测试的工具" />
    </div>
  </el-drawer>
</template>

<style lang="scss" scoped>
.test-panel {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.tool-info {
  h4 {
    margin: 0 0 8px;
    font-size: 16px;
    color: #303133;
  }

  .tool-desc {
    margin: 0 0 12px;
    font-size: 13px;
    color: #909399;
  }

  .tool-sig {
    background: #f5f7fa;
    padding: 8px 12px;
    border-radius: 4px;

    code {
      font-family: 'Courier New', monospace;
      font-size: 12px;
      color: #409eff;
    }
  }
}

.params-section {
  h4 {
    margin: 0 0 12px;
    font-size: 14px;
    color: #303133;
  }
}

.param-inputs {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.param-input-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.param-label {
  font-size: 13px;
  color: #606266;
  font-weight: 500;

  .param-type {
    color: #909399;
    font-size: 12px;
  }
}

.no-args {
  padding: 12px 0;
  text-align: center;
}

.test-actions {
  display: flex;
  gap: 8px;
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
    margin-bottom: 12px;

    .result-duration {
      font-size: 12px;
      color: #909399;
    }
  }

  .result-data,
  .result-error {
    border: 1px solid #e4e7ed;
    border-radius: 4px;
    padding: 12px;
    background: #fafafa;
  }

  .result-label {
    font-size: 12px;
    color: #909399;
    margin-bottom: 8px;
  }

  .result-json {
    margin: 0;
    font-family: 'Courier New', monospace;
    font-size: 12px;
    color: #303133;
    white-space: pre-wrap;
    word-break: break-all;
  }
}

.no-tool {
  padding: 48px 0;
}
</style>
