<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useKnowledgeStore } from '@/stores/knowledge'
import type { RetrievalSettingsPayload } from '@/types/knowledge'

function debounce<T extends (...args: any[]) => any>(fn: T, delay: number): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout> | null = null
  return (...args: Parameters<T>) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delay)
  }
}

interface Props {
  kbId: string
}

const props = defineProps<Props>()
const router = useRouter()
const knowledgeStore = useKnowledgeStore()

type SettingsValue = string | number | boolean
type SettingsKey =
  | 'method'
  | 'final_top_k'
  | 'vector_top_k'
  | 'keyword_top_k'
  | 'similarity_threshold'
  | 'vector_weight'
  | 'keyword_weight'
  | 'rrf_k'
  | 'rerank_enabled'
  | 'rerank_top_n'
  | 'rerank_trigger_threshold'
  | 'navigation_enabled'
  | 'nav_anchor_count'
  | 'nav_confidence_threshold'

type SettingsForm = Record<SettingsKey, SettingsValue>
type NumericSettingsKey = Exclude<SettingsKey, 'method' | 'rerank_enabled' | 'navigation_enabled'>

interface ModelOption {
  id: string
  name: string
  prov: string
  use: 'embedding' | 'rerank'
  enabled: boolean
  dim?: number
}

interface NumericField {
  key: NumericSettingsKey
  label: string
  min: number
  max: number
  step: number
  integer?: boolean
}

const defaults: SettingsForm = {
  method: 'hybrid',
  final_top_k: 5,
  vector_top_k: 20,
  keyword_top_k: 20,
  similarity_threshold: 0.0,
  vector_weight: 0.7,
  keyword_weight: 0.3,
  rrf_k: 60,
  rerank_enabled: true,
  rerank_top_n: 10,
  rerank_trigger_threshold: 0.02,
  navigation_enabled: true,
  nav_anchor_count: 3,
  nav_confidence_threshold: 0.15
}

const form = reactive<SettingsForm>({ ...defaults })
const initialValues = reactive<SettingsForm>({ ...defaults })
const embeddingModelId = ref('')
const rerankModelId = ref('')
const initialEmbeddingModelId = ref('')
const initialRerankModelId = ref('')
const saving = ref(false)
const rebuilding = ref(false)

const modelCatalog: ModelOption[] = [
  { id: 'model-embedding', name: 'BGE-M3', prov: 'local', use: 'embedding', enabled: true, dim: 1024 },
  { id: 'model-embedding-1024-b', name: 'Qwen3-Embedding', prov: 'local', use: 'embedding', enabled: true, dim: 1024 },
  { id: 'model-embedding-768', name: 'MiniLM-768', prov: 'local', use: 'embedding', enabled: true, dim: 768 },
  { id: 'model-embedding-disabled', name: 'BGE-Base Disabled', prov: 'local', use: 'embedding', enabled: false, dim: 1024 },
  { id: 'model-rerank', name: 'BGE-Reranker', prov: 'local', use: 'rerank', enabled: true },
  { id: 'model-rerank-b', name: 'Qwen3-Reranker', prov: 'local', use: 'rerank', enabled: true },
  { id: 'model-rerank-disabled', name: 'Legacy Reranker', prov: 'local', use: 'rerank', enabled: false }
]

const embeddingModels = computed(() =>
  modelCatalog.filter((model) => model.use === 'embedding' && model.enabled && model.dim === 1024)
)
const rerankModels = computed(() =>
  modelCatalog.filter((model) => model.use === 'rerank' && model.enabled)
)

const numericFields: NumericField[] = [
  { key: 'final_top_k', label: '最终 TopK', min: 1, max: 50, step: 1, integer: true },
  { key: 'vector_top_k', label: '向量候选 TopK', min: 1, max: 200, step: 1, integer: true },
  { key: 'keyword_top_k', label: '关键词候选 TopK', min: 1, max: 200, step: 1, integer: true },
  { key: 'rrf_k', label: 'RRF K', min: 1, max: 500, step: 1, integer: true },
  { key: 'rerank_top_n', label: '候选数量', min: 1, max: 100, step: 1, integer: true },
  { key: 'nav_anchor_count', label: '锚点数量', min: 1, max: 20, step: 1, integer: true }
]

watch(() => props.kbId, () => {
  void load()
})

onMounted(() => {
  void load()
})

async function load(): Promise<void> {
  await knowledgeStore.loadRetrievalSettings(props.kbId)
  hydrate(true)
}

function hydrate(updateModels: boolean): void {
  const resolved = knowledgeStore.retrievalSettings?.resolved || {}
  ;(Object.keys(defaults) as SettingsKey[]).forEach((key) => {
    const value = resolved[key]
    form[key] = typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? value : defaults[key]
    initialValues[key] = form[key]
  })
  if (updateModels) {
    embeddingModelId.value = knowledgeStore.retrievalSettings?.embedding_model?.id || ''
    rerankModelId.value = knowledgeStore.retrievalSettings?.rerank_model?.id || ''
    initialEmbeddingModelId.value = embeddingModelId.value
    initialRerankModelId.value = rerankModelId.value
  }
}

// Auto-save with debounce (500ms)
const debouncedSave = debounce(async () => {
  if (!validate()) return
  const retrievalConfig: Record<string, unknown> = {}
  ;(Object.keys(defaults) as SettingsKey[]).forEach((key) => {
    if (!valuesEqual(form[key], initialValues[key])) retrievalConfig[key] = form[key]
  })
  const payload: RetrievalSettingsPayload = {}
  if (Object.keys(retrievalConfig).length) payload.retrieval_config = retrievalConfig
  if (Object.keys(payload).length) {
    try {
      saving.value = true
      await knowledgeStore.saveRetrievalSettings(props.kbId, payload)
      hydrate(false)
      ElMessage.success('检索设置已自动保存')
    } finally {
      saving.value = false
    }
  }
}, 500)

watch(() => form, () => {
  debouncedSave()
}, { deep: true })

function sourceFor(key: SettingsKey): '测试覆盖' | '知识库' | '场景' | '系统默认' {
  const source = knowledgeStore.retrievalSettings?.values[key]?.source
  if (source === 'override') return '测试覆盖'
  if (source === 'knowledge_base') return '知识库'
  if (source === 'scene') return '场景'
  return '系统默认'
}

function modelSource(kind: 'embedding' | 'rerank'): '测试覆盖' | '知识库' | '场景' | '系统默认' {
  const changed = kind === 'embedding'
    ? embeddingModelId.value !== initialEmbeddingModelId.value
    : rerankModelId.value !== initialRerankModelId.value
  return changed ? '知识库' : '系统默认'
}

const methodDescription = computed(() => {
  const desc: Record<string, string> = {
    vector: '已切换至向量检索：基于语义相似度匹配',
    keyword: '已切换至关键词检索：基于关键词精确匹配',
    hybrid: '已切换至混合检索：融合向量与关键词结果'
  }
  return desc[form.method as string] || ''
})

function valuesEqual(left: SettingsValue, right: SettingsValue): boolean {
  return left === right
}

function normalizeWeight(value: number): number {
  return Math.round(value * 100) / 100
}

function syncVectorWeight(value: number | number[]): void {
  if (!Array.isArray(value) && Number.isFinite(value)) {
    form.vector_weight = normalizeWeight(value)
    form.keyword_weight = normalizeWeight(1 - value)
  }
}

function syncKeywordWeight(value: number | number[]): void {
  if (!Array.isArray(value) && Number.isFinite(value)) {
    form.keyword_weight = normalizeWeight(value)
    form.vector_weight = normalizeWeight(1 - value)
  }
}

function validate(): boolean {
  for (const field of numericFields) {
    const value = form[field.key]
    if (typeof value !== 'number' || !Number.isFinite(value) || value < field.min || value > field.max) {
      ElMessage.error(`${field.label}必须在 ${field.min}-${field.max} 之间`)
      return false
    }
    if (field.integer && !Number.isInteger(value)) {
      ElMessage.error(`${field.label}必须是整数`)
      return false
    }
  }
  const similarityThreshold = form.similarity_threshold as number
  const vectorWeight = form.vector_weight as number
  const keywordWeight = form.keyword_weight as number
  const rerankThreshold = form.rerank_trigger_threshold as number
  const navigationThreshold = form.nav_confidence_threshold as number

  if (similarityThreshold < 0 || similarityThreshold > 1) {
    ElMessage.error('分数阈值必须在 0-1 之间')
    return false
  }
  if (vectorWeight < 0 || vectorWeight > 1 || keywordWeight < 0 || keywordWeight > 1) {
    ElMessage.error('向量与关键词权重必须在 0-1 之间')
    return false
  }
  if (normalizeWeight(vectorWeight + keywordWeight) !== 1) {
    ElMessage.error('向量权重与关键词权重之和必须为 1')
    return false
  }
  if (rerankThreshold < 0 || rerankThreshold > 1) {
    ElMessage.error('Rerank 触发阈值必须在 0-1 之间')
    return false
  }
  if (navigationThreshold < 0 || navigationThreshold > 1) {
    ElMessage.error('导航置信度必须在 0-1 之间')
    return false
  }
  return true
}

async function save(): Promise<void> {
  if (!validate()) return
  const retrievalConfig: Record<string, unknown> = {}
  ;(Object.keys(defaults) as SettingsKey[]).forEach((key) => {
    if (!valuesEqual(form[key], initialValues[key])) retrievalConfig[key] = form[key]
  })
  const embeddingChanged =
    embeddingModelId.value !== initialEmbeddingModelId.value &&
    Boolean(initialEmbeddingModelId.value) &&
    Boolean(embeddingModelId.value)
  const payload: RetrievalSettingsPayload = {}
  if (Object.keys(retrievalConfig).length) payload.retrieval_config = retrievalConfig
  if (embeddingModelId.value !== initialEmbeddingModelId.value) {
    payload.embedding_model_id = embeddingModelId.value || null
  }
  if (rerankModelId.value !== initialRerankModelId.value) {
    payload.rerank_model_id = rerankModelId.value || null
  }
  if (!Object.keys(payload).length) {
    ElMessage.info('暂无配置变更')
    return
  }

  let rebuildRequired = false
  if (embeddingChanged) {
    try {
      await ElMessageBox.confirm(
        '更换 Embedding 模型后需重建向量，旧向量不能用于新模型检索。',
        '重建提示',
        { confirmButtonText: '保存并重建向量', cancelButtonText: '仅保存', type: 'warning' }
      )
      rebuildRequired = true
    } catch (error) {
      rebuildRequired = false
    }
  }

  saving.value = true
  try {
    await knowledgeStore.saveRetrievalSettings(props.kbId, payload)
    hydrate(false)
    initialEmbeddingModelId.value = embeddingModelId.value
    initialRerankModelId.value = rerankModelId.value
    ElMessage.success('检索设置已保存')
    if (rebuildRequired) await rebuildAll(true)
  } finally {
    saving.value = false
  }
}

async function rebuildAll(skipConfirm = false): Promise<void> {
  if (!skipConfirm) {
    try {
      await ElMessageBox.confirm('将重建当前知识库全部分段向量，任务可能在后台运行。', '风险操作确认', {
        confirmButtonText: '重建全部向量',
        cancelButtonText: '取消',
        type: 'warning'
      })
    } catch (error) {
      return
    }
  }
  rebuilding.value = true
  try {
    await knowledgeStore.queueReembedding(props.kbId, [], [])
    ElMessage.success('向量重建任务已排队')
  } finally {
    rebuilding.value = false
  }
}

function openKbForm(): void {
  router.push('/knowledge')
}
</script>

<template>
  <section v-loading="saving || rebuilding" class="retrieval-settings-tab">
    <div class="settings-grid">
      <section class="setting-panel">
        <h3>索引模型</h3>
        <el-form label-position="top">
          <el-form-item>
            <template #label>
              <span class="field-label">
                Embedding 模型
                <el-tooltip :content="modelSource('embedding')" placement="top">
                  <el-tag size="small" type="info">{{ modelSource('embedding') }}</el-tag>
                </el-tooltip>
              </span>
            </template>
            <el-select v-model="embeddingModelId" filterable class="full-width">
              <el-option
                v-for="model in embeddingModels"
                :key="model.id"
                :label="`${model.name} / ${model.dim}维`"
                :value="model.id"
              />
            </el-select>
          </el-form-item>
        </el-form>
      </section>

      <section class="setting-panel">
        <h3>检索策略</h3>
        <el-form label-position="top">
          <el-form-item>
            <template #label>
              <span class="field-label">
                检索模式
                <el-tooltip :content="sourceFor('method')" placement="top">
                  <el-tag size="small" type="info">{{ sourceFor('method') }}</el-tag>
                </el-tooltip>
              </span>
            </template>
            <el-radio-group v-model="form.method">
              <el-radio-button value="vector">向量</el-radio-button>
              <el-radio-button value="keyword">关键词</el-radio-button>
              <el-radio-button value="hybrid">混合</el-radio-button>
            </el-radio-group>
            <div class="method-description">{{ methodDescription }}</div>
          </el-form-item>
          <div class="field-grid">
            <el-form-item v-for="field in numericFields.slice(0, 3)" :key="field.key">
              <template #label>
                <span class="field-label">
                  {{ field.label }}
                  <el-tooltip :content="sourceFor(field.key)" placement="top">
                    <el-tag size="small" type="info">{{ sourceFor(field.key) }}</el-tag>
                  </el-tooltip>
                </span>
              </template>
              <el-input-number
                v-model="form[field.key] as number"
                :min="field.min"
                :max="field.max"
                :step="field.step"
                :precision="field.integer ? 0 : undefined"
                class="full-width"
              />
            </el-form-item>
          </div>
          <el-form-item>
            <template #label>
              <span class="field-label">
                分数阈值
                <el-tooltip :content="sourceFor('similarity_threshold')" placement="top">
                  <el-tag size="small" type="info">{{ sourceFor('similarity_threshold') }}</el-tag>
                </el-tooltip>
              </span>
            </template>
            <el-slider v-model="form.similarity_threshold as number" :min="0" :max="1" :step="0.01" show-input />
          </el-form-item>
          <el-form-item>
            <template #label>
              <span class="field-label">
                向量权重
                <el-tooltip :content="sourceFor('vector_weight')" placement="top">
                  <el-tag size="small" type="info">{{ sourceFor('vector_weight') }}</el-tag>
                </el-tooltip>
              </span>
            </template>
            <el-slider
              :model-value="form.vector_weight as number"
              :min="0"
              :max="1"
              :step="0.05"
              show-input
              @update:model-value="syncVectorWeight"
            />
          </el-form-item>
          <el-form-item>
            <template #label>
              <span class="field-label">
                关键词权重
                <el-tooltip :content="sourceFor('keyword_weight')" placement="top">
                  <el-tag size="small" type="info">{{ sourceFor('keyword_weight') }}</el-tag>
                </el-tooltip>
              </span>
            </template>
            <el-slider
              :model-value="form.keyword_weight as number"
              :min="0"
              :max="1"
              :step="0.05"
              show-input
              @update:model-value="syncKeywordWeight"
            />
          </el-form-item>
          <el-form-item>
            <template #label>
              <span class="field-label">
                RRF K
                <el-tooltip :content="sourceFor('rrf_k')" placement="top">
                  <el-tag size="small" type="info">{{ sourceFor('rrf_k') }}</el-tag>
                </el-tooltip>
              </span>
            </template>
            <el-input-number v-model="form.rrf_k as number" :min="1" :max="500" :step="1" :precision="0" class="full-width" />
          </el-form-item>
        </el-form>
      </section>

      <section class="setting-panel">
        <h3>Rerank</h3>
        <el-form label-position="top">
          <el-form-item>
            <template #label>
              <span class="field-label">
                启用 Rerank
                <el-tooltip :content="sourceFor('rerank_enabled')" placement="top">
                  <el-tag size="small" type="info">{{ sourceFor('rerank_enabled') }}</el-tag>
                </el-tooltip>
              </span>
            </template>
            <el-switch v-model="form.rerank_enabled" />
          </el-form-item>
          <el-form-item>
            <template #label>
              <span class="field-label">
                Rerank 模型
                <el-tooltip :content="modelSource('rerank')" placement="top">
                  <el-tag size="small" type="info">{{ modelSource('rerank') }}</el-tag>
                </el-tooltip>
              </span>
            </template>
            <el-select v-model="rerankModelId" filterable class="full-width">
              <el-option v-for="model in rerankModels" :key="model.id" :label="model.name" :value="model.id" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <template #label>
              <span class="field-label">
                候选数量
                <el-tooltip :content="sourceFor('rerank_top_n')" placement="top">
                  <el-tag size="small" type="info">{{ sourceFor('rerank_top_n') }}</el-tag>
                </el-tooltip>
              </span>
            </template>
            <el-input-number v-model="form.rerank_top_n as number" :min="1" :max="100" :step="1" :precision="0" class="full-width" />
          </el-form-item>
          <el-form-item>
            <template #label>
              <span class="field-label">
                触发阈值
                <el-tooltip :content="sourceFor('rerank_trigger_threshold')" placement="top">
                  <el-tag size="small" type="info">{{ sourceFor('rerank_trigger_threshold') }}</el-tag>
                </el-tooltip>
              </span>
            </template>
            <el-slider v-model="form.rerank_trigger_threshold as number" :min="0" :max="1" :step="0.01" show-input />
          </el-form-item>
        </el-form>
      </section>

      <section class="setting-panel">
        <h3>结构导航</h3>
        <el-form label-position="top">
          <el-form-item>
            <template #label>
              <span class="field-label">
                启用导航
                <el-tooltip :content="sourceFor('navigation_enabled')" placement="top">
                  <el-tag size="small" type="info">{{ sourceFor('navigation_enabled') }}</el-tag>
                </el-tooltip>
              </span>
            </template>
            <el-switch v-model="form.navigation_enabled" />
          </el-form-item>
          <el-form-item>
            <template #label>
              <span class="field-label">
                锚点数量
                <el-tooltip :content="sourceFor('nav_anchor_count')" placement="top">
                  <el-tag size="small" type="info">{{ sourceFor('nav_anchor_count') }}</el-tag>
                </el-tooltip>
              </span>
            </template>
            <el-input-number v-model="form.nav_anchor_count as number" :min="1" :max="20" :step="1" :precision="0" class="full-width" />
          </el-form-item>
          <el-form-item>
            <template #label>
              <span class="field-label">
                置信度阈值
                <el-tooltip :content="sourceFor('nav_confidence_threshold')" placement="top">
                  <el-tag size="small" type="info">{{ sourceFor('nav_confidence_threshold') }}</el-tag>
                </el-tooltip>
              </span>
            </template>
            <el-slider v-model="form.nav_confidence_threshold as number" :min="0" :max="1" :step="0.01" show-input />
          </el-form-item>
        </el-form>
      </section>

      <section class="setting-panel risk-panel">
        <h3>风险操作</h3>
        <div class="risk-actions">
          <el-button type="warning" icon="Refresh" :loading="rebuilding" @click="rebuildAll()">
            重建全部向量
          </el-button>
          <el-button icon="Link" @click="openKbForm">打开知识库表单</el-button>
        </div>
        <div class="readonly-grid">
          <el-form-item label="分块大小（V1 只读）">
            <el-input model-value="--" disabled />
          </el-form-item>
          <el-form-item label="分块重叠（V1 只读）">
            <el-input model-value="--" disabled />
          </el-form-item>
        </div>
      </section>
    </div>

    <div class="save-row">
      <el-button type="primary" :loading="saving" @click="save">保存设置</el-button>
    </div>
  </section>
</template>

<style lang="scss" scoped>
.retrieval-settings-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  align-items: start;
}

.setting-panel {
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 16px;

  h3 {
    margin: 0 0 14px;
    color: var(--el-text-color-primary);
    font-size: 16px;
  }
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0 12px;
}

.field-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.full-width {
  width: 100%;
}

.risk-panel {
  grid-column: 1 / -1;
}

.risk-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}

.readonly-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.save-row {
  display: flex;
  justify-content: flex-end;
  background: transparent;
}

@media (max-width: 900px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .field-grid,
  .readonly-grid {
    grid-template-columns: 1fr;
  }

  .save-row {
    justify-content: flex-start;
  }
}
</style>