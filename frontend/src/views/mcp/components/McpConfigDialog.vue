<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { Mcp, McpEnv } from '@/types/mcp'

interface Props {
  visible: boolean
  data?: Mcp | null
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  data: null
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [data: Partial<Mcp>]
}>()

const formRef = ref()
const loading = ref(false)

const form = reactive({
  name: '',
  tp: 'stdio' as 'stdio' | 'SSE',
  cmd: '',
  timeout: 30,
  env: [] as McpEnv[]
})

const rules = {
  name: [
    { required: true, message: '请输入 MCP 名称', trigger: 'blur' },
    { min: 2, max: 50, message: '名称长度为 2-50 个字符', trigger: 'blur' }
  ],
  tp: [
    { required: true, message: '请选择 MCP 类型', trigger: 'change' }
  ],
  cmd: [
    { required: true, message: '请输入命令或 URL', trigger: 'blur' }
  ],
  timeout: [
    { required: true, message: '请输入超时时间', trigger: 'blur' }
  ]
}

const typeOptions = [
  { label: 'stdio', value: 'stdio' },
  { label: 'SSE', value: 'SSE' }
]

// 根据类型获取命令提示
const cmdPlaceholder = computed(() => {
  if (form.tp === 'stdio') {
    return '如 npx -y @mcp/server-filesystem'
  } else {
    return '如 https://api.mcp.example.com/server'
  }
})

// 监听 visible 变化，重置表单
watch(() => props.visible, (val) => {
  if (val) {
    if (props.data) {
      // 编辑模式，填充数据
      form.name = props.data.name
      form.tp = props.data.tp
      form.cmd = props.data.cmd
      form.timeout = props.data.timeout
      form.env = [...props.data.env]
    } else {
      // 新建模式，重置表单
      form.name = ''
      form.tp = 'stdio'
      form.cmd = ''
      form.timeout = 30
      form.env = []
    }
  }
})

function handleClose() {
  emit('update:visible', false)
}

// 添加环境变量
function addEnv() {
  form.env.push({ k: '', v: '' })
}

// 删除环境变量
function removeEnv(index: number) {
  form.env.splice(index, 1)
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  // 验证环境变量
  const validEnv = form.env.filter(e => e.k.trim())
  if (validEnv.length !== form.env.length) {
    ElMessage.warning('环境变量 key 不能为空')
    return
  }

  loading.value = true

  try {
    emit('submit', {
      ...form,
      env: validEnv
    })
    emit('update:visible', false)
  } catch (error: any) {
    ElMessage.error(error.message || '保存失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="data ? '编辑 MCP 服务' : '添加 MCP 服务'"
    width="600px"
    :close-on-click-modal="false"
    @update:model-value="handleClose"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="80px"
    >
      <el-form-item label="名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入 MCP 名称" maxlength="50" show-word-limit />
      </el-form-item>

      <el-form-item label="类型" prop="tp">
        <el-radio-group v-model="form.tp">
          <el-radio
            v-for="item in typeOptions"
            :key="item.value"
            :value="item.value"
          >
            {{ item.label }}
          </el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="命令/URL" prop="cmd">
        <el-input
          v-model="form.cmd"
          :placeholder="cmdPlaceholder"
          maxlength="500"
        />
      </el-form-item>

      <el-form-item label="超时(秒)" prop="timeout">
        <el-input-number
          v-model="form.timeout"
          :min="5"
          :max="300"
          :step="5"
          style="width: 100%"
        />
      </el-form-item>

      <el-form-item label="环境变量">
        <div class="env-section">
          <div v-if="form.env.length === 0" class="env-empty">
            暂无环境变量
          </div>
          <div v-for="(env, index) in form.env" :key="index" class="env-row">
            <el-input
              v-model="env.k"
              placeholder="Key"
              style="flex: 1"
            />
            <span class="env-separator">=</span>
            <el-input
              v-model="env.v"
              placeholder="Value"
              type="password"
              show-password
              style="flex: 1; margin-left: 8px"
            />
            <el-button
              type="danger"
              icon="Delete"
              size="small"
              @click="removeEnv(index)"
              style="margin-left: 8px"
            />
          </div>
          <el-button type="primary" icon="Plus" size="small" @click="addEnv">
            添加环境变量
          </el-button>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">
        确定
      </el-button>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
.env-section {
  width: 100%;
}

.env-empty {
  color: #909399;
  font-size: 13px;
  padding: 8px 0;
}

.env-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.env-separator {
  color: #909399;
  margin: 0 8px;
}
</style>
