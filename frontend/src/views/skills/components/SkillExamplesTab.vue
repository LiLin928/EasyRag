<script setup lang="ts">
import { ref, watch } from 'vue'

interface Props {
  data: { q: string; a: string }[]
  readonly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  readonly: false
})

const emit = defineEmits<{
  update: [examples: { q: string; a: string }[]]
}>()

const examples = ref<{ q: string; a: string }[]>([])

// 监听数据变化
watch(() => props.data, (data) => {
  if (data && data.length > 0) {
    examples.value = data.map(e => ({ q: e.q, a: e.a }))
  } else {
    // 默认显示一个空示例对
    examples.value = [{ q: '', a: '' }]
  }
}, { immediate: true, deep: true })

// 监听示例变化
watch(examples, (newExamples) => {
  emit('update', newExamples)
}, { deep: true })

function addExample() {
  examples.value.push({ q: '', a: '' })
}

function removeExample(index: number) {
  if (examples.value.length > 1) {
    examples.value.splice(index, 1)
  }
}

function moveUp(index: number) {
  if (index > 0) {
    const temp = examples.value[index]
    examples.value[index] = examples.value[index - 1]
    examples.value[index - 1] = temp
  }
}

function moveDown(index: number) {
  if (index < examples.value.length - 1) {
    const temp = examples.value[index]
    examples.value[index] = examples.value[index + 1]
    examples.value[index + 1] = temp
  }
}
</script>

<template>
  <div class="examples-tab">
    <div v-if="examples.length === 0" class="empty-state">
      <el-empty description="暂无示例" :image-size="80" />
      <el-button v-if="!readonly" type="primary" icon="Plus" @click="addExample">
        添加示例
      </el-button>
    </div>

    <div v-else class="examples-list">
      <div
        v-for="(example, index) in examples"
        :key="index"
        class="example-item"
      >
        <div class="example-header">
          <span class="example-number">示例 {{ index + 1 }}</span>
          <div class="example-actions">
            <el-button
              v-if="!readonly"
              size="small"
              icon="Top"
              :disabled="index === 0"
              @click="moveUp(index)"
            />
            <el-button
              v-if="!readonly"
              size="small"
              icon="Bottom"
              :disabled="index === examples.length - 1"
              @click="moveDown(index)"
            />
            <el-button
              v-if="!readonly"
              size="small"
              icon="Delete"
              type="danger"
              :disabled="examples.length === 1"
              @click="removeExample(index)"
            />
          </div>
        </div>

        <div class="example-content">
          <div class="field-group">
            <label>问题</label>
            <el-input
              v-model="example.q"
              type="textarea"
              :rows="2"
              placeholder="请输入示例问题"
              :disabled="readonly"
            />
          </div>

          <div class="field-group">
            <label>答案</label>
            <el-input
              v-model="example.a"
              type="textarea"
              :rows="3"
              placeholder="请输入示例答案"
              :disabled="readonly"
            />
          </div>
        </div>
      </div>

      <el-button
        v-if="!readonly"
        type="primary"
        icon="Plus"
        @click="addExample"
        style="width: 100%; margin-top: 12px"
      >
        添加示例
      </el-button>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.examples-tab {
  padding: 16px;
  height: 100%;
  overflow-y: auto;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
}

.examples-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.example-item {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 12px;
  background: #fafafa;
}

.example-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e0e0e0;
}

.example-number {
  font-weight: 600;
  color: #409eff;
}

.example-actions {
  display: flex;
  gap: 4px;
}

.example-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 4px;

  label {
    font-size: 13px;
    color: #606266;
    font-weight: 500;
  }
}
</style>
