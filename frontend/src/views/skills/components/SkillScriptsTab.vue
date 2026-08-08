<script setup lang="ts">
import { ref, watch } from 'vue'

interface Props {
  data: { name: string; content: string }[]
  readonly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  readonly: false
})

const emit = defineEmits<{
  update: [scripts: { name: string; content: string }[]]
}>()

const scripts = ref<{ name: string; content: string }[]>([])
const newScriptName = ref('')

// 监听数据变化
watch(() => props.data, (data) => {
  if (data) {
    scripts.value = data.map(s => ({ name: s.name, content: s.content || '' }))
  } else {
    scripts.value = []
  }
}, { immediate: true, deep: true })

// 监听脚本变化
watch(scripts, (newScripts) => {
  emit('update', newScripts)
}, { deep: true })

function addScript() {
  if (newScriptName.value.trim()) {
    scripts.value.push({ name: newScriptName.value.trim(), content: '' })
    newScriptName.value = ''
  }
}

function removeScript(index: number) {
  scripts.value.splice(index, 1)
}

function moveUp(index: number) {
  if (index > 0) {
    const temp = scripts.value[index]
    scripts.value[index] = scripts.value[index - 1]
    scripts.value[index - 1] = temp
  }
}

function moveDown(index: number) {
  if (index < scripts.value.length - 1) {
    const temp = scripts.value[index]
    scripts.value[index] = scripts.value[index + 1]
    scripts.value[index + 1] = temp
  }
}
</script>

<template>
  <div class="scripts-tab">
    <div v-if="scripts.length === 0" class="empty-state">
      <el-empty description="暂无关联脚本" :image-size="80" />
    </div>

    <div v-else class="scripts-list">
      <div
        v-for="(script, index) in scripts"
        :key="index"
        class="script-item"
      >
        <div class="script-header">
          <el-icon class="script-icon"><Document /></el-icon>
          <el-input
            v-model="script.name"
            class="script-name-input"
            placeholder="脚本名称（如：数据处理.js）"
            :disabled="readonly"
          />
          <div class="script-actions">
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
              :disabled="index === scripts.length - 1"
              @click="moveDown(index)"
            />
            <el-button
              v-if="!readonly"
              size="small"
              icon="Delete"
              type="danger"
              @click="removeScript(index)"
            />
          </div>
        </div>

        <el-input
          v-model="script.content"
          type="textarea"
          class="script-code"
          :rows="6"
          resize="vertical"
          placeholder="// 在此编写脚本代码"
          :disabled="readonly"
        />
      </div>
    </div>

    <div v-if="!readonly" class="add-script">
      <el-input
        v-model="newScriptName"
        placeholder="输入脚本名称（如：数据处理.js）"
        @keyup.enter="addScript"
      >
        <template #append>
          <el-button icon="Plus" @click="addScript">添加</el-button>
        </template>
      </el-input>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.scripts-tab {
  padding: 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.scripts-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
  overflow-y: auto;
}

.script-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
  border: 1px solid #e0e0e0;
}

.script-header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.script-icon {
  color: #409eff;
  font-size: 16px;
  flex-shrink: 0;
}

.script-name-input {
  flex: 1;

  :deep(.el-input__wrapper) {
    background: #fff;
  }

  :deep(.el-input__inner) {
    font-size: 14px;
    color: #303133;
    font-weight: 500;
  }
}

.script-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.script-code {
  width: 100%;

  :deep(.el-textarea__inner) {
    font-family: 'Courier New', Consolas, monospace;
    font-size: 13px;
    line-height: 1.5;
    background: #fff;
  }
}

.add-script {
  margin-top: auto;
}
</style>
