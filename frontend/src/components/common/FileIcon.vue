<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  ext: string
  size?: number
}

const props = withDefaults(defineProps<Props>(), {
  size: 32
})

const extColors: Record<string, { bg: string; color: string }> = {
  pdf: { bg: '#fef2f2', color: '#DC2626' },
  doc: { bg: '#eff6ff', color: '#2563eb' },
  docx: { bg: '#eff6ff', color: '#2563eb' },
  xls: { bg: '#f0fdf4', color: '#16A34A' },
  xlsx: { bg: '#f0fdf4', color: '#16A34A' },
  md: { bg: '#f9fafb', color: '#374151' },
  txt: { bg: '#f9fafb', color: '#6b7280' },
  html: { bg: '#fef3c7', color: '#D97706' }
}

const colors = computed(() => {
  const key = props.ext.toLowerCase()
  return extColors[key] || { bg: '#f3f4f6', color: '#6b7280' }
})

const icon = computed(() => {
  const ext = props.ext.toLowerCase()
  if (['pdf'].includes(ext)) return 'Document'
  if (['doc', 'docx'].includes(ext)) return 'Document'
  if (['xls', 'xlsx'].includes(ext)) return 'Document'
  if (['md'].includes(ext)) return 'Document'
  return 'Document'
})
</script>

<template>
  <div
    class="file-icon"
    :style="{
      width: size + 'px',
      height: size + 'px',
      backgroundColor: colors.bg
    }"
  >
    <el-icon :size="size * 0.5" :color="colors.color">
      <component :is="icon" />
    </el-icon>
    <span class="file-ext" :style="{ color: colors.color }">{{ ext.toUpperCase() }}</span>
  </div>
</template>

<style lang="scss" scoped>
.file-icon {
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
}

.file-ext {
  font-size: 8px;
  font-weight: 600;
  position: absolute;
  bottom: 2px;
}
</style>
