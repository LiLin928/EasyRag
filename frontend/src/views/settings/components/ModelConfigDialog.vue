<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { ModelGroup, ModelDef } from '@/types/settings'
import { PROVIDERS, USE_OPTIONS } from '@/types/settings'

interface Props {
  visible: boolean
  group: ModelGroup
  data?: ModelDef | null
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  data: null
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [data: ModelDef]
}>()

const formRef = ref()
const loading = ref(false)

const form = reactive<ModelDef>({
  name: '',
  prov: 'dashscope',
  use: 'qa',
  temp: 0.7,
  ctx: '32768',
  dim: '1024',
  def: false,
  url: '',
  key: '',
  params: {}
})

const rules = {
  name: [
    { required: true, message: '请输入模型名称', trigger: 'blur' },
    { min: 2, max: 100, message: '名称长度为 2-100 个字符', trigger: 'blur' }
  ],
  prov: [
    { required: true, message: '请选择供应商', trigger: 'change' }
  ],
  use: [
    { required: true, message: '请选择用途', trigger: 'change' }
  ],
  url: [
    { required: true, message: '请输入 API 地址', trigger: 'blur' }
  ]
}

// 根据分组动态生成用途选项
const useOptions = computed(() => USE_OPTIONS[props.group] || [])

// 是否显示温度字段（仅 LLM 组）
const showTemp = computed(() => props.group === 'llm')

// 是否显示维度字段（仅 Embedding 组）
const showDim = computed(() => props.group === 'embed')

// 监听 visible 变化，重置表单
watch(() => props.visible, (val) => {
  if (val) {
    if (props.data) {
      // 编辑模式，填充数据
      Object.assign(form, props.data)
      // 确保 params 是对象
      if (typeof form.params !== 'object' || form.params === null) {
        form.params = {}
      }
    } else {
      // 新建模式，重置表单
      form.name = ''
      form.prov = 'dashscope'
      form.use = useOptions.value[0]?.value || ''
      form.temp = 0.7
      form.ctx = '32768'
      form.dim = '1024'
      form.def = false
      form.url = ''
      form.key = ''
      form.params = {}
    }
  }
})

function handleClose() {
  emit('update:visible', false)
}

// 添加动态参数
function addParam() {
  const key = 'param_' + Date.now()
  form.params[key] = ''
}

// 删除动态参数
function removeParam(key: string) {
  delete form.params[key]
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  // 清理空参数
  const cleanParams: Record<string, string> = {}
  Object.entries(form.params).forEach(([key, value]) => {
    if (key.trim() && value.trim()) {
      cleanParams[key] = value
    }
  })
  form.params = cleanParams

  loading.value = true

  try {
    emit('submit', { ...form })
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
    :title="data ? '编辑模型' : '添加模型'"
    width="600px"
    :close-on-click-modal="false"
    @update:model-value="handleClose"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="100px"
    >
      <el-form-item label="模型名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入模型名称" maxlength="100" show-word-limit />
      </el-form-item>

      <el-form-item label="供应商" prop="prov">
        <el-select v-model="form.prov" placeholder="选择供应商" style="width: 100%">
          <el-option
            v-for="item in PROVIDERS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="用途" prop="use">
        <el-select v-model="form.use" placeholder="选择用途" style="width: 100%">
          <el-option
            v-for="item in useOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>

      <!-- 温度字段（仅 LLM 组显示） -->
      <el-form-item v-if="showTemp" label="温度" prop="temp">
        <el-input-number
          v-model="form.temp"
          :min="0"
          :max="2"
          :step="0.1"
          :precision="1"
          placeholder="0.7"
          style="width: 100%"
        />
      </el-form-item>

      <!-- 维度字段（仅 Embedding 组显示） -->
      <el-form-item v-if="showDim" label="维度" prop="dim">
        <el-input v-model="form.dim" placeholder="如：1024" maxlength="10" />
      </el-form-item>

      <el-form-item label="上下文长度" prop="ctx">
        <el-input v-model="form.ctx" placeholder="如：32768" maxlength="10" />
      </el-form-item>

      <el-form-item label="API 地址" prop="url">
        <el-input v-model="form.url" placeholder="https://api.example.com/v1" />
      </el-form-item>

      <el-form-item label="密钥">
        <el-input
          v-model="form.key"
          type="password"
          placeholder="请输入密钥"
          show-password
          clearable
        />
      </el-form-item>

      <el-form-item label="高级参数">
        <div class="params-section">
          <div v-if="Object.keys(form.params).length === 0" class="params-empty">
            暂无自定义参数
          </div>
          <div v-for="(_, key) in form.params" :key="key" class="param-row">
            <el-input
              :model-value="key"
              placeholder="参数名"
              style="flex: 2"
              @input="(val: string) => { if(val && val !== key) { const temp = form.params[key]; delete form.params[key]; form.params[val] = temp; } }"
            />
            <el-input
              v-model="form.params[key]"
              placeholder="参数值"
              style="flex: 1; margin-left: 8px"
            />
            <el-button
              type="danger"
              icon="Delete"
              size="small"
              @click="removeParam(key)"
            />
          </div>
          <el-button type="primary" icon="Plus" size="small" @click="addParam">
            添加参数
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
</style>
