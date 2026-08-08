<script setup lang="ts">
interface Props {
  title?: string
  message?: string
}

withDefaults(defineProps<Props>(), {
  title: '确认删除',
  message: '删除后不可恢复，确定要删除吗？'
})

const emit = defineEmits<{
  confirm: []
}>()

function handleConfirm() {
  emit('confirm')
}
</script>

<template>
  <el-popconfirm
    :title="message"
    confirm-button-text="删除"
    cancel-button-text="取消"
    confirm-button-type="danger"
    @confirm="handleConfirm"
  >
    <template #reference>
      <el-button type="danger" size="small" icon="Delete">
        删除
      </el-button>
    </template>
  </el-popconfirm>
</template>
