<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { Tool, ToolParam, ToolAuth } from '@/types/tool'

interface Props {
  visible: boolean
  data?: Tool | null
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  data: null
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [data: Partial<Tool>]
}>()

const formRef = ref()
const loading = ref(false)

const form = reactive({
  name: '',
  type: 'HTTP' as 'HTTP' | '内置' | 'Python',
  desc: '',
  sig: '',
  enabled: true,
  params: [] as ToolParam[],
  auth: {
    mode: 'none' as 'none' | 'apikey' | 'bearer',
    key: ''
  } as ToolAuth
})

const rules = {
  name: [
    { required: true, message: '请输入工具名称', trigger: 'blur' },
    { min: 2, max: 50, message: '名称长度为 2-50 个字符', trigger: 'blur' }
  ],
  type: [
    { required: true, message: '请选择工具类型', trigger: 'change' }
  ],
  sig: [
    { required: true, message: '请输入函数签名', trigger: 'blur' }
  ]
}

const typeOptions = [
  { label: 'HTTP', value: 'HTTP' },
  { label: '内置', value: '内置' },
  { label: 'Python', value: 'Python' }
]

const authModeOptions = [
  { label: '无鉴权', value: 'none' },
  { label: 'API Key', value: 'apikey' },
  { label: 'Bearer Token', value: 'bearer' }
]

// 监听 visible 变化，重置表单
watch(() => props.visible, (val) => {
  if (val) {
    if (props.data) {
      // 编辑模式，填充数据
      form.name = props.data.name
      form.type = props.data.type
      form.desc = props.data.desc
      form.sig = props.data.sig
      form.enabled = props.data.enabled
      form.params = [...props.data.params]
      form.auth = { ...props.data.auth }
    } else {
      // 新建模式，重置表单
      form.name = ''
      form.type = 'HTTP'
      form.desc = ''
      form.sig = ''
      form.enabled = true
      form.params = []
      form.auth = { mode: 'none', key: '' }
    }
  }
})

function handleClose() {
  emit('update:visible', false)
}

// 添加参数
function addParam() {
  form.params.push({ n: '', t: 'string', d: '' })
}

// 删除参数
function removeParam(index: number) {
  form.params.splice(index, 1)
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  // 验证参数
  const validParams = form.params.filter(p => p.n.trim())
  if (validParams.length !== form.params.length) {
    ElMessage.warning('参数名不能为空')
    return
  }

  loading.value = true

  try {
    emit('submit', {
      ...form,
      params: validParams
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
    :title="data ? '编辑工具' : '新建工具'"
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
        <el-input v-model="form.name" placeholder="请输入工具名称" maxlength="50" show-word-limit />
      </el-form-item>

      <el-form-item label="类型" prop="type">
        <el-select v-model="form.type" placeholder="选择工具类型">
          <el-option
            v-for="item in typeOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="描述" prop="desc">
        <el-input
          v-model="form.desc"
          type="textarea"
          placeholder="请输入工具描述"
          :rows="2"
          maxlength="200"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="签名" prop="sig">
        <el-input
          v-model="form.sig"
          placeholder="例如: functionName(param1: string): Promise<Result>"
          maxlength="200"
        />
      </el-form-item>

      <el-form-item label="状态">
        <el-switch v-model="form.enabled" active-text="启用" inactive-text="停用" />
      </el-form-item>

      <el-form-item label="参数">
        <div class="params-section">
          <div v-if="form.params.length === 0" class="params-empty">
            暂无参数
          </div>
          <div v-for="(param, index) in form.params" :key="index" class="param-row">
            <el-input
              v-model="param.n"
              placeholder="参数名"
              style="flex: 2"
            />
            <el-select
              v-model="param.t"
              placeholder="类型"
              style="flex: 1; margin: 0 8px"
            >
              <el-option label="string" value="string" />
              <el-option label="number" value="number" />
              <el-option label="boolean" value="boolean" />
              <el-option label="object" value="object" />
              <el-option label="array" value="array" />
            </el-select>
            <el-input
              v-model="param.d"
              placeholder="默认值"
              style="flex: 1; margin-right: 8px"
            />
            <el-button
              type="danger"
              icon="Delete"
              size="small"
              @click="removeParam(index)"
            />
          </div>
          <el-button type="primary" icon="Plus" size="small" @click="addParam">
            添加参数
          </el-button>
        </div>
      </el-form-item>

      <el-form-item label="鉴权">
        <div class="auth-section">
          <el-select v-model="form.auth.mode" placeholder="选择鉴权方式" style="width: 200px; margin-bottom: 8px">
            <el-option
              v-for="item in authModeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <el-input
            v-if="form.auth.mode !== 'none'"
            v-model="form.auth.key"
            placeholder="请输入密钥"
            type="password"
            show-password
            clearable
          />
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
.params-section {
  width: 100%;
}

.params-empty {
  color: #909399;
  font-size: 13px;
  padding: 8px 0;
}

.param-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.auth-section {
  display: flex;
  flex-direction: column;
}
</style>
