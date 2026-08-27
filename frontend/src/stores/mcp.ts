import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as mcpApi from '@/api/mcp'
import type { Mcp, McpTestResult } from '@/types/mcp'

export const useMcpStore = defineStore('mcp', () => {
  // ========== 状态 ==========
  const mcps = ref<Mcp[]>([])
  const loading = ref(false)
  const currentMcp = ref<Mcp | null>(null)
  const keyword = ref('')

  // ========== 计算属性 ==========

  // 按关键词过滤的 MCP 列表（名称 / 命令或 URL）
  const filteredMcps = computed(() => {
    if (!keyword.value.trim()) return mcps.value
    const kw = keyword.value.toLowerCase()
    return mcps.value.filter(m =>
      m.name.toLowerCase().includes(kw) ||
      (m.cmd || '').toLowerCase().includes(kw)
    )
  })

  // ========== MCP 操作 ==========

  async function loadMcps() {
    loading.value = true
    try {
      mcps.value = await mcpApi.getMcps()
    } finally {
      loading.value = false
    }
  }

  async function loadMcp(id: string) {
    currentMcp.value = await mcpApi.getMcp(id)
    return currentMcp.value
  }

  async function createMcp(data: Partial<Mcp>) {
    const mcp = await mcpApi.createMcp(data)
    mcps.value.unshift(mcp)
    return mcp
  }

  async function updateMcp(id: string, data: Partial<Mcp>) {
    const mcp = await mcpApi.updateMcp(id, data)
    const index = mcps.value.findIndex(m => m.id === id)
    if (index > -1) {
      mcps.value[index] = mcp
    }
    return mcp
  }

  async function deleteMcp(id: string) {
    await mcpApi.deleteMcp(id)
    mcps.value = mcps.value.filter(m => m.id !== id)
  }

  async function toggleMcp(id: string, status: 'on' | 'off') {
    const mcp = await mcpApi.updateMcp(id, { status })
    const index = mcps.value.findIndex(m => m.id === id)
    if (index > -1) {
      mcps.value[index] = mcp
    }
    return mcp
  }

  async function testMcp(id: string): Promise<McpTestResult> {
    return await mcpApi.testMcp(id)
  }

  // ========== 重置状态 ==========

  function reset() {
    mcps.value = []
    currentMcp.value = null
    loading.value = false
    keyword.value = ''
  }

  return {
    // 状态
    mcps,
    loading,
    currentMcp,
    keyword,
    filteredMcps,

    // 操作
    loadMcps,
    loadMcp,
    createMcp,
    updateMcp,
    deleteMcp,
    toggleMcp,
    testMcp,

    // 重置
    reset
  }
})
