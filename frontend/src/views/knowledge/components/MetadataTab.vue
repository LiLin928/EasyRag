<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useKnowledgeStore } from '@/stores/knowledge'
import type { MetadataField, MetadataScope, MetadataFieldType } from '@/types/knowledge'

const props = defineProps<{ kbId: string }>()
const knowledgeStore = useKnowledgeStore()

const loading = ref(false)
const dialogVisible = ref(false)
const editingField = ref<MetadataField | null>(null)

const form = ref({
  key: '',
  name: '',
  scope: 'document' as MetadataScope,
  dataType: 'string' as MetadataFieldType,
  options: '',
  required: false,
  filterable: true,
  retrievalFilterable: false,
  visible: true
})

const docFields = computed(() => knowledgeStore.metadataFields.filter(f => f.scope === 'document').sort((a, b) => a.sortOrder - b.sortOrder))
const chunkFields = computed(() => knowledgeStore.metadataFields.filter(f => f.scope === 'chunk').sort((a, b) => a.sortOrder - b.sortOrder))

const dataTypeOptions = [
    { label: '字符串', value: 'string' },
    { label: '数字', value: 'number' },
    { label: '日期', value: 'date' },
    { label: '下拉选择', value: 'select' },
    { label: '布尔值', value: 'boolean' }
  ]

onMounted(async () => {
  loading.value = true
  try {
    await knowledgeStore.loadMetadataFields(props.kbId)
  } finally {
    loading.value = false
  }
})

async function handleToggle(field: MetadataField, key: 'visible' | 'filterable' | 'retrievalFilterable') {
  try {
    await knowledgeStore.updateMetadataField(field.id, { [key]: field[key] })
  } catch {
    field[key] = !field[key]
  }
}

function openCreateDialog(scope: MetadataScope) {
  editingField.value = null
  form.value = {
    key: '',
    name: '',
    scope,
    dataType: 'string',
    options: '',
    required: false,
    filterable: true,
    retrievalFilterable: false,
    visible: true
  }
  dialogVisible.value = true
}

function openEditDialog(field: MetadataField) {
  editingField.value = field
  form.value = {
    key: field.key,
    name: field.name,
    scope: field.scope,
    dataType: field.dataType,
    options: field.options.join(', '),
    required: field.required,
    filterable: field.filterable,
    retrievalFilterable: field.retrievalFilterable,
    visible: field.visible
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.value.key || !form.value.name) {
    ElMessage.warning('字段标识和名称不能为空')
    return
  }

  const data: Partial<MetadataField> = {
    key: form.value.key,
    name: form.value.name,
    scope: form.value.scope,
    dataType: form.value.dataType,
    options: form.value.dataType === 'select' ? form.value.options.split(',').map(s => s.trim()).filter(Boolean) : [],
    required: form.value.required,
    filterable: form.value.filterable,
    retrievalFilterable: form.value.retrievalFilterable,
    visible: form.value.visible,
    builtIn: false
  }

  try {
    if (editingField.value) {
      await knowledgeStore.updateMetadataField(editingField.value.id, data)
      ElMessage.success('更新成功')
    } else {
      await knowledgeStore.createMetadataField(props.kbId, data)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleDelete(field: MetadataField) {
  try {
    await ElMessageBox.confirm('确定要删除字段"' + field.name + '"吗？', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await knowledgeStore.deleteMetadataField(field.id)
    ElMessage.success('删除成功')
  } catch {
    // cancelled
  }
}
</script>

<template>
  <div v-loading="loading" class="metadata-tab">
    <!-- 文档级元数据 -->
    <div class="scope-section">
      <div class="scope-header">
        <h3 class="section-title">文档级元数据</h3>
        <el-button type="primary" size="small" @click="openCreateDialog('document')">
          添加字段
        </el-button>
      </div>
      <el-table :data="docFields" border style="width: 100%">
        <el-table-column prop="name" label="字段名称" width="140" />
        <el-table-column prop="key" label="标识" width="140" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            {{ dataTypeOptions.find(o => o.value === row.dataType)?.label || row.dataType }}
          </template>
        </el-table-column>
        <el-table-column label="选项" min-width="200">
          <template #default="{ row }">
            <span v-if="row.dataType === 'select'">{{ row.options.join(', ') }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="必填" width="60" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.required" size="small" type="danger">必填</el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="可见" width="60" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.visible" size="small" :disabled="row.builtIn" @change="handleToggle(row as MetadataField, 'visible')" />
          </template>
        </el-table-column>
        <el-table-column label="可筛选" width="70" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.filterable" size="small" @change="handleToggle(row as MetadataField, 'filterable')" />
          </template>
        </el-table-column>
        <el-table-column label="检索过滤" width="80" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.retrievalFilterable" size="small" @change="handleToggle(row as MetadataField, 'retrievalFilterable')" />
          </template>
        </el-table-column>
        <el-table-column label="内置" width="60" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.builtIn" size="small" type="info">内置</el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEditDialog(row as MetadataField)">编辑</el-button>
            <el-button v-if="!row.builtIn" link type="danger" size="small" @click="handleDelete(row as MetadataField)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分段级元数据 -->
    <div class="scope-section">
      <div class="scope-header">
        <h3 class="section-title">分段级元数据</h3>
        <el-button type="primary" size="small" @click="openCreateDialog('chunk')">添加字段</el-button>
      </div>
      <el-table :data="chunkFields" border style="width: 100%">
        <el-table-column prop="name" label="字段名称" width="140" />
        <el-table-column prop="key" label="标识" width="140" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            {{ dataTypeOptions.find(o => o.value === row.dataType)?.label || row.dataType }}
          </template>
        </el-table-column>
        <el-table-column label="选项" min-width="200">
          <template #default="{ row }">
            <span v-if="row.dataType === 'select'">{{ row.options.join(', ') }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="必填" width="60" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.required" size="small" type="danger">必填</el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="可见" width="60" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.visible" size="small" :disabled="row.builtIn" @change="handleToggle(row as MetadataField, 'visible')" />
          </template>
        </el-table-column>
        <el-table-column label="可筛选" width="70" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.filterable" size="small" @change="handleToggle(row as MetadataField, 'filterable')" />
          </template>
        </el-table-column>
        <el-table-column label="检索过滤" width="80" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.retrievalFilterable" size="small" @change="handleToggle(row as MetadataField, 'retrievalFilterable')" />
          </template>
        </el-table-column>
        <el-table-column label="内置" width="60" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.builtIn" size="small" type="info">内置</el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEditDialog(row as MetadataField)">编辑</el-button>
            <el-button v-if="!row.builtIn" link type="danger" size="small" @click="handleDelete(row as MetadataField)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 创建/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingField ? '编辑字段' : '添加字段'"
      width="500px"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="字段标识">
          <el-input v-model="form.key" placeholder="如 project_name" :disabled="!!editingField" />
        </el-form-item>
        <el-form-item label="字段名称">
          <el-input v-model="form.name" placeholder="如 项目名称" />
        </el-form-item>
        <el-form-item label="作用域">
          <el-radio-group v-model="form.scope" :disabled="!!editingField">
            <el-radio value="document">文档级</el-radio>
            <el-radio value="chunk">分段级</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="数据类型">
          <el-select v-model="form.dataType" style="width: 100%">
            <el-option v-for="o in dataTypeOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.dataType === 'select'" label="选项列表">
          <el-input v-model="form.options" placeholder="用逗号分隔，如 选项A, 选项B" />
        </el-form-item>
        <el-form-item label="必填">
          <el-switch v-model="form.required" />
        </el-form-item>
        <el-form-item label="可见">
          <el-switch v-model="form.visible" />
        </el-form-item>
        <el-form-item label="可筛选">
          <el-switch v-model="form.filterable" />
        </el-form-item>
        <el-form-item label="检索过滤">
          <el-switch v-model="form.retrievalFilterable" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.scope-section {
  margin-bottom: 24px;

  .scope-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;

    .section-title {
      margin: 0;
      font-size: 15px;
      font-weight: 600;
      color: #303133;
    }
  }
}

.text-muted {
  color: #c0c4cc;
  font-size: 12px;
}
</style>
