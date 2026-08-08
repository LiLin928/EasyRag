import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as toolApi from '@/api/tool'
import type { Tool, ToolTestArgs, ToolTestResult } from '@/types/tool'

export const useToolStore = defineStore('tool', () => {
  // ========== 状态 ==========
  const tools = ref<Tool[]>([])
  const loading = ref(false)
  const currentTool = ref<Tool | null>(null)

  // ========== 工具操作 ==========

  async function loadTools() {
    loading.value = true
    try {
      tools.value = await toolApi.getTools()
    } finally {
      loading.value = false
    }
  }

  async function loadTool(id: string) {
    currentTool.value = await toolApi.getTool(id)
    return currentTool.value
  }

  async function createTool(data: Partial<Tool>) {
    const tool = await toolApi.createTool(data)
    tools.value.unshift(tool)
    return tool
  }

  async function updateTool(id: string, data: Partial<Tool>) {
    const tool = await toolApi.updateTool(id, data)
    const index = tools.value.findIndex(t => t.id === id)
    if (index > -1) {
      tools.value[index] = tool
    }
    return tool
  }

  async function deleteTool(id: string) {
    await toolApi.deleteTool(id)
    tools.value = tools.value.filter(t => t.id !== id)
  }

  async function toggleTool(id: string, enabled: boolean) {
    const tool = await toolApi.updateTool(id, { enabled })
    const index = tools.value.findIndex(t => t.id === id)
    if (index > -1) {
      tools.value[index] = tool
    }
    return tool
  }

  async function testTool(id: string, args: ToolTestArgs): Promise<ToolTestResult> {
    return await toolApi.testTool(id, args)
  }

  // ========== 重置状态 ==========

  function reset() {
    tools.value = []
    currentTool.value = null
    loading.value = false
  }

  return {
    // 状态
    tools,
    loading,
    currentTool,

    // 操作
    loadTools,
    loadTool,
    createTool,
    updateTool,
    deleteTool,
    toggleTool,
    testTool,

    // 重置
    reset
  }
})
