<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useKnowledgeStore } from '@/stores/knowledge'
import * as settingsApi from '@/api/settings'
import type { ModelDef } from '@/types/settings'
import type { ChunkMethod, RetrievalMethod, RetrievalSettings, EffectiveValue } from '@/types/knowledge'

const props = defineProps<{ kbId: string }>()
const knowledgeStore = useKnowledgeStore()

const loading = ref(false)
const saving = ref(false)
const embedModels = ref<ModelDef[]>([])
const rerankModels = ref<ModelDef[]>([])

const form = reactive({
  chunkMethod: 'general' as ChunkMethod,
  chunkSize: 500,
  chunkOverlap: 50,
  embeddingModel: '',
  retrievalMode: 'hybrid' as RetrievalMethod,
  vectorWeight: 0.7,
  keywordWeight: 0.3,
  rerankEnabled: true,
  rerankModel: '',
  rerankTopN: 5,
  topK: 10,
  scoreThresholdEnabled: true,
  scoreThreshold: 0.5
})

const chunkMethodOptions = [
  { value: 'general', label: '通用', desc: '将文档按固定长度分块，适用于大多数场景' },
  { value: 'parent_child', label: '父子分段', desc: '大块上下文 + 小块精确召回，兼顾上下文与精度' },
  { value: 'qa', label: '问答对', desc: '按问答对提取分段，适合 FAQ 类文档' }
]

const retrievalModeOptions = [
  { value: 'vector', label: '向量检索', desc: '基于语义相似度，理解同义词和语义关系' },
  { value: 'keyword', label: '全文检索', desc: '基于关键词精确匹配，适合专业术语' },
  { value: 'hybrid', label: '混合检索', desc: '同时使用向量+全文检索，加权融合后精排' }
]

const isHybrid = computed(() => form.retrievalMode === 'hybrid')

onMounted(async () => {
  loading.value = true
  try {
    const [, embeds, reranks] = await Promise.all([
      knowledgeStore.loadRetrievalSettings(props.kbId),
      settingsApi.getModelsByGroup('embed'),
      settingsApi.getModelsByGroup('rerank')
    ])
    embedModels.value = embeds
    rerankModels.value = reranks

    const s = knowledgeStore.retrievalSettings
    if (s) {
      form.chunkMethod = s.chunkMethod
      form.chunkSize = s.chunkSize
      form.chunkOverlap = s.chunkOverlap
      form.embeddingModel = s.embeddingModel
      form.rerankModel = s.rerankModel
      form.retrievalMode = (s.config.method as EffectiveValue<string>)?.value as RetrievalMethod || 'hybrid'
      form.vectorWeight = (s.config.vectorWeight as EffectiveValue<number>)?.value ?? 0.7
      form.keywordWeight = (s.config.keywordWeight as EffectiveValue<number>)?.value ?? 0.3
      form.rerankEnabled = (s.config.rerankEnabled as EffectiveValue<boolean>)?.value ?? true
      form.rerankTopN = (s.config.rerankTopN as EffectiveValue<number>)?.value ?? 5
      form.topK = (s.config.vectorTopK as EffectiveValue<number>)?.value ?? 10
      form.scoreThresholdEnabled = (s.config.similarityThresholdEnabled as EffectiveValue<boolean>)?.value ?? true
      form.scoreThreshold = (s.config.similarityThreshold as EffectiveValue<number>)?.value ?? 0.5
    }
  } finally {
    loading.value = false
  }
})

async function handleSave() {
  saving.value = true
  try {
    const data: Partial<RetrievalSettings> = {
      embeddingModel: form.embeddingModel,
      rerankModel: form.rerankModel,
      chunkMethod: form.chunkMethod,
      chunkSize: form.chunkSize,
      chunkOverlap: form.chunkOverlap,
      config: {
        method: { value: form.retrievalMode, source: 'knowledge_base' },
        vectorTopK: { value: form.topK, source: 'knowledge_base' },
        similarityThreshold: { value: form.scoreThreshold, source: 'knowledge_base' },
        similarityThresholdEnabled: { value: form.scoreThresholdEnabled, source: 'knowledge_base' },
        vectorWeight: { value: form.vectorWeight, source: 'knowledge_base' },
        keywordWeight: { value: form.keywordWeight, source: 'knowledge_base' },
        rerankEnabled: { value: form.rerankEnabled, source: 'knowledge_base' },
        rerankTopN: { value: form.rerankTopN, source: 'knowledge_base' }
      }
    }
    await knowledgeStore.saveRetrievalSettings(props.kbId, data)
    ElMessage.success('检索设置保存成功')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-loading="loading" class="settings-tab">
    <el-form label-width="120px" label-position="right">
      <!-- 分段设置 -->
      <div class="settings-section">
        <h3 class="section-title">分段设置</h3>
        <el-form-item label="分段方式">
          <div class="card-group">
            <div
              v-for="opt in chunkMethodOptions"
              :key="opt.value"
              class="mode-card"
              :class="{ active: form.chunkMethod === opt.value }"
              @click="form.chunkMethod = opt.value as ChunkMethod"
            >
              <el-icon v-if="form.chunkMethod === opt.value" class="check-icon"><Check /></el-icon>
              <span class="card-label">{{ opt.label }}</span>
              <span class="card-desc">{{ opt.desc }}</span>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="分块大小">
          <el-input-number v-model="form.chunkSize" :min="100" :max="2000" :step="50" />
          <span class="form-hint">字符数</span>
        </el-form-item>
        <el-form-item label="分块重叠">
          <el-input-number v-model="form.chunkOverlap" :min="0" :max="500" :step="10" />
          <span class="form-hint">字符数</span>
        </el-form-item>
      </div>

      <!-- 索引设置 -->
      <div class="settings-section">
        <h3 class="section-title">索引设置</h3>
        <el-form-item label="Embedding 模型">
          <el-select v-model="form.embeddingModel" placeholder="选择 Embedding 模型" style="width: 320px">
            <el-option
              v-for="m in embedModels"
              :key="m.name"
              :label="m.name + ' (' + m.dim + '维)'"
              :value="m.name"
            />
          </el-select>
        </el-form-item>
      </div>

      <!-- 检索设置 -->
      <div class="settings-section">
        <h3 class="section-title">检索设置</h3>
        <el-form-item label="检索模式">
          <div class="card-group">
            <div
              v-for="opt in retrievalModeOptions"
              :key="opt.value"
              class="mode-card"
              :class="{ active: form.retrievalMode === opt.value }"
              @click="form.retrievalMode = opt.value as RetrievalMethod"
            >
              <el-icon v-if="form.retrievalMode === opt.value" class="check-icon"><Check /></el-icon>
              <span class="card-label">{{ opt.label }}</span>
              <span class="card-desc">{{ opt.desc }}</span>
            </div>
          </div>
        </el-form-item>

        <el-form-item v-if="isHybrid" label="向量权重">
          <div class="slider-row">
            <el-input-number v-model="form.vectorWeight" :min="0" :max="1" :step="0.05" :precision="2" style="width: 140px" />
            <el-slider v-model="form.vectorWeight" :min="0" :max="1" :step="0.05" style="width: 300px" />
          </div>
        </el-form-item>

        <el-form-item v-if="isHybrid" label="关键词权重">
          <div class="slider-row">
            <el-input-number v-model="form.keywordWeight" :min="0" :max="1" :step="0.05" :precision="2" style="width: 140px" />
            <el-slider v-model="form.keywordWeight" :min="0" :max="1" :step="0.05" style="width: 300px" />
          </div>
        </el-form-item>

        <el-form-item label="Rerank">
          <el-switch v-model="form.rerankEnabled" />
          <el-select
            v-if="form.rerankEnabled"
            v-model="form.rerankModel"
            placeholder="选择 Rerank 模型"
            style="width: 320px; margin-left: 16px"
          >
            <el-option
              v-for="m in rerankModels"
              :key="m.name"
              :label="m.name"
              :value="m.name"
            />
          </el-select>
        </el-form-item>

        <el-form-item v-if="form.rerankEnabled" label="Rerank TopN">
          <el-input-number v-model="form.rerankTopN" :min="1" :max="50" />
        </el-form-item>

        <el-form-item label="TopK">
          <div class="slider-row">
            <el-input-number v-model="form.topK" :min="1" :max="50" style="width: 100px" />
            <el-slider v-model="form.topK" :min="1" :max="50" style="width: 300px" />
          </div>
        </el-form-item>

        <el-form-item label="分数阈值">
          <el-switch v-model="form.scoreThresholdEnabled" />
          <template v-if="form.scoreThresholdEnabled">
            <div class="slider-row" style="margin-left: 16px">
              <el-input-number v-model="form.scoreThreshold" :min="0" :max="1" :step="0.05" :precision="2" style="width: 140px" />
              <el-slider v-model="form.scoreThreshold" :min="0" :max="1" :step="0.01" style="width: 300px" />
            </div>
          </template>
        </el-form-item>
      </div>

      <div class="settings-footer">
        <el-button type="primary" :loading="saving" @click="handleSave">保存设置</el-button>
      </div>
    </el-form>
  </div>
</template>

<style lang="scss" scoped>
.settings-tab {
  padding: 8px 0;
}

.settings-section {
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #ebeef5;

  &:last-child {
    border-bottom: none;
  }

  .section-title {
    margin: 0 0 16px;
    font-size: 15px;
    font-weight: 600;
    color: #303133;
  }
}

.card-group {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.mode-card {
  width: 220px;
  padding: 12px 16px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;

  &:hover {
    border-color: #409eff;
  }

  &.active {
    border-color: #409eff;
    background: #ecf5ff;
  }

  .check-icon {
    position: absolute;
    top: 8px;
    right: 8px;
    color: #409eff;
  }

  .card-label {
    font-size: 14px;
    font-weight: 600;
    color: #303133;
  }

  .card-desc {
    font-size: 12px;
    color: #909399;
    line-height: 1.4;
  }
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.form-hint {
  margin-left: 8px;
  font-size: 12px;
  color: #909399;
}

.settings-footer {
  margin-top: 24px;
  padding-top: 16px;
}
</style>
