<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { RetrievalTestCase, RetrievalTestCasePayload, Document } from '@/types/knowledge'
import { useKnowledgeStore } from '@/stores/knowledge'
import FileIcon from '@/components/common/FileIcon.vue'

const props = defineProps<{
  modelValue: boolean
  setId: string
  editCase?: RetrievalTestCase | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'saved': []
}>()

const knowledgeStore = useKnowledgeStore()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const form = ref<RetrievalTestCasePayload>({})
const saving = ref(false)

const enabledDocs = computed<Document[]>(() =>
  knowledgeStore.docList.filter(d => d.enabled)
)

watch(() => props.modelValue, (open) => {
  if (!open) return
  if (props.editCase) {
    form.value = {
      query: props.editCase.query,
      expected_doc_ids: [...props.editCase.expected_doc_ids],
      tags: [...props.editCase.tags],
      enabled: props.editCase.enabled,
      sort_order: props.editCase.sort_order
    }
  } else {
    form.value = {
      query: '',
      expected_doc_ids: [],
      tags: [],
      enabled: true,
      sort_order: 0
    }
  }
})

const tagInput = ref('')

function handleTagConfirm() {
  const val = tagInput.value.trim()
  if (val && !form.value.tags?.includes(val)) {
    form.value.tags = [...(form.value.tags || []), val]
  }
  tagInput.value = ''
}

function removeTag(tag: string) {
  form.value.tags = (form.value.tags || []).filter(t => t !== tag)
}

async function handleSave() {
  if (!form.value.query?.trim()) return
  saving.value = true
  try {
    await knowledgeStore.saveTestCase(
      props.setId,
      { ...form.value, query: form.value.query!.trim() },
      props.editCase?.id
    )
    visible.value = false
    emit('saved')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="editCase ? '编辑用例' : '新建用例'"
    width="600px"
    :append-to-body="true"
    destroy-on-close
  >
    <el-form label-width="100px" @submit.prevent="handleSave">
      <el-form-item label="查询" required>
        <el-input
          v-model="form.query"
          type="textarea"
          :rows="3"
          placeholder="输入检索查询文本"
        />
      </el-form-item>

      <el-form-item label="期望文档">
        <el-select
          v-model="form.expected_doc_ids"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="选择期望命中的文档"
          style="width: 100%"
        >
          <el-option
            v-for="doc in enabledDocs"
            :key="doc.id"
            :label="doc.name"
            :value="doc.id"
          >
            <div style="display:flex;align-items:center;gap:8px">
              <FileIcon :ext="doc.ext" :size="20" />
              <span>{{ doc.name }}</span>
            </div>
          </el-option>
        </el-select>
      </el-form-item>

      <el-form-item label="标签">
        <div class="tags-area">
          <el-tag
            v-for="tag in (form.tags || [])"
            :key="tag"
            closable
            size="small"
            style="margin: 2px"
            @close="removeTag(tag)"
          >
            {{ tag }}
          </el-tag>
          <el-input
            v-model="tagInput"
            size="small"
            style="width: 120px"
            placeholder="添加标签"
            @keyup.enter="handleTagConfirm"
          />
        </div>
      </el-form-item>

      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>

      <el-form-item label="排序号">
        <el-input-number v-model="form.sort_order" :min="0" :step="1" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="!form.query?.trim()" @click="handleSave">
        保存
      </el-button>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
.tags-area {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}
</style>
