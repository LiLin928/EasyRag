<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { Skill, SkillScript } from '@/types/skill'
import SkillBasicTab from './SkillBasicTab.vue'
import SkillExamplesTab from './SkillExamplesTab.vue'
import SkillScriptsTab from './SkillScriptsTab.vue'
import SkillMountsTab from './SkillMountsTab.vue'
import SkillBudgetBar from './SkillBudgetBar.vue'

interface Props {
  visible: boolean
  data?: Skill | null
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  data: null
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [data: Partial<Skill>]
}>()

const activeTab = ref('basic')
const loading = ref(false)
const basicFormRef = ref()
const examplesFormRef = ref()
const scriptsFormRef = ref()
const mountsFormRef = ref()

const form = reactive({
  ico: '🔧',
  name: '',
  scope: 'custom' as 'builtin' | 'custom',
  ver: '1.0.0',
  desc: '',
  trigger: '',
  prompt: '',
  tools: [] as string[],
  docs: [] as string[],
  wfs: [] as string[],
  examples: [] as { q: string; a: string }[],
  scripts: [] as SkillScript[],
  budget: undefined as number | undefined
})

// 是否为内置技能
const isBuiltin = computed(() => props.data?.scope === 'builtin')

// 监听 visible 变化，重置表单
watch(() => props.visible, (val) => {
  if (val) {
    if (props.data) {
      // 编辑模式，填充数据
      Object.assign(form, {
        ico: props.data.ico,
        name: props.data.name,
        scope: props.data.scope,
        ver: props.data.ver,
        desc: props.data.desc,
        trigger: props.data.trigger,
        prompt: props.data.prompt,
        tools: [...props.data.tools],
        docs: [...props.data.docs],
        wfs: [...props.data.wfs],
        examples: [...props.data.examples],
        scripts: [...props.data.scripts],
        budget: props.data.budget
      })
      // 内置技能只能编辑部分字段
      if (isBuiltin.value) {
        activeTab.value = 'basic'
      }
    } else {
      // 新建模式，重置表单
      form.ico = '🔧'
      form.name = ''
      form.scope = 'custom'
      form.ver = '1.0.0'
      form.desc = ''
      form.trigger = ''
      form.prompt = ''
      form.tools = []
      form.docs = []
      form.wfs = []
      form.examples = []
      form.scripts = []
      form.budget = undefined
    }
  }
})

function handleClose() {
  emit('update:visible', false)
}

async function handleSubmit() {
  // 验证所有表单
  const basicValid = await basicFormRef.value?.validate().catch(() => false)
  if (!basicValid) {
    activeTab.value = 'basic'
    ElMessage.warning('请完善基础信息')
    return
  }

  // 内置技能不允许修改
  if (isBuiltin.value) {
    ElMessage.warning('内置技能只能查看或复制为自定义技能')
    return
  }

  loading.value = true

  try {
    const submitData = {
      ico: form.ico,
      name: form.name,
      desc: form.desc,
      trigger: form.trigger,
      prompt: form.prompt,
      tools: form.tools,
      docs: form.docs,
      wfs: form.wfs,
      examples: form.examples.filter(e => e.q.trim() && e.a.trim()),
      scripts: form.scripts,
      budget: form.budget
    }

    emit('submit', submitData)
    emit('update:visible', false)
  } catch (error: any) {
    ElMessage.error(error.message || '保存失败')
  } finally {
    loading.value = false
  }
}

// 从示例Tab更新示例
function updateExamples(examples: { q: string; a: string }[]) {
  form.examples = examples
}

// 从挂载Tab更新挂载
function updateMounts(mounts: { tools: string[]; docs: string[]; wfs: string[] }) {
  form.tools = mounts.tools
  form.docs = mounts.docs
  form.wfs = mounts.wfs
}

// 从脚本Tab更新脚本
function updateScripts(scripts: SkillScript[]) {
  form.scripts = scripts
}

// 从基础Tab更新基础信息
function updateBasic(basic: any) {
  Object.assign(form, basic)
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="data ? (isBuiltin ? '查看内置技能' : '编辑技能') : '新建技能'"
    width="800px"
    :close-on-click-modal="false"
    @update:model-value="handleClose"
  >
    <el-tabs v-model="activeTab" class="config-tabs">
      <el-tab-pane label="基础信息" name="basic">
        <SkillBasicTab
          ref="basicFormRef"
          :data="form"
          :readonly="isBuiltin"
          @update="updateBasic"
        />
      </el-tab-pane>

      <el-tab-pane label="问答示例" name="examples">
        <SkillExamplesTab
          ref="examplesFormRef"
          :data="form.examples"
          :readonly="isBuiltin"
          @update="updateExamples"
        />
      </el-tab-pane>

      <el-tab-pane label="关联脚本" name="scripts">
        <SkillScriptsTab
          ref="scriptsFormRef"
          :data="form.scripts"
          :readonly="isBuiltin"
          @update="updateScripts"
        />
      </el-tab-pane>

      <el-tab-pane label="资源挂载" name="mounts">
        <SkillMountsTab
          ref="mountsFormRef"
          :tools="form.tools"
          :docs="form.docs"
          :wfs="form.wfs"
          :readonly="isBuiltin"
          @update="updateMounts"
        />
      </el-tab-pane>

      <el-tab-pane label="预算配置" name="budget">
        <SkillBudgetBar
          :budget="form.budget"
          :used="data?.used"
          :skill-id="data?.id"
          :readonly="isBuiltin"
          @update="form.budget = $event"
        />
      </el-tab-pane>
    </el-tabs>

    <template #footer>
      <div class="drawer-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button
          v-if="!isBuiltin"
          type="primary"
          :loading="loading"
          @click="handleSubmit"
        >
          保存
        </el-button>
        <el-button
          v-if="isBuiltin"
          type="success"
          @click="$emit('submit', { ...form, scope: 'custom' as const, name: form.name + ' (副本)' }); $emit('update:visible', false)"
        >
          复制为自定义技能
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
.config-tabs {
  min-height: 450px;

  :deep(.el-tabs__content) {
    height: calc(100% - 40px);
    padding: 0;
  }

  :deep(.el-tab-pane) {
    height: 100%;
    overflow-y: auto;
  }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>

