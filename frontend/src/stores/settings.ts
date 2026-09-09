import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as settingsApi from '@/api/settings'
import type { ModelGroup, ModelDef, Scene } from '@/types/settings'

export const useSettingsStore = defineStore('settings', () => {
  // ========== 状态 ==========
  const models = ref<Record<ModelGroup, ModelDef[]>>({
    llm: [],
    embed: [],
    rerank: []
  })
  const scenes = ref<Scene[]>([])
  const loading = ref(false)
  const activeGroup = ref<ModelGroup>('llm')

  // ========== 模型操作 ==========

  async function loadModels() {
    loading.value = true
    try {
      const data = await settingsApi.getModels()
      models.value = data
    } finally {
      loading.value = false
    }
  }

  async function saveModel(group: ModelGroup, model: ModelDef) {
    const updated = await settingsApi.saveModel(group, model)
    const index = models.value[group].findIndex(m => m.name === model.name)
    if (index > -1) {
      models.value[group][index] = updated
    } else {
      models.value[group].push(updated)
    }
    return updated
  }

  async function setDefault(group: ModelGroup, name: string) {
    await settingsApi.setDefault(group, name)
    // 更新本地状态
    models.value[group].forEach(m => {
      m.def = m.name === name
    })
  }

  async function deleteModel(group: ModelGroup, name: string) {
    await settingsApi.deleteModel(group, name)
    models.value[group] = models.value[group].filter(m => m.name !== name)
  }

  // ========== 场景操作 ==========

  async function loadScenes() {
    loading.value = true
    try {
      scenes.value = await settingsApi.getScenes()
    } finally {
      loading.value = false
    }
  }

  async function saveScene(scene: Scene) {
    const updated = await settingsApi.saveScene(scene)
    const index = scenes.value.findIndex(s => s.id === scene.id)
    if (index > -1) {
      scenes.value[index] = updated
    } else {
      scenes.value.push(updated)
    }
    return updated
  }

  async function deleteScene(id: string) {
    await settingsApi.deleteScene(id)
    scenes.value = scenes.value.filter(s => s.id !== id)
  }

  // ========== 辅助方法 ==========

  function getModelsByGroup(group: ModelGroup): ModelDef[] {
    return models.value[group] || []
  }

  function getDefaultModel(group: ModelGroup): ModelDef | undefined {
    return models.value[group]?.find(m => m.def)
  }

  // ========== 重置状态 ==========

  function reset() {
    models.value = {
      llm: [],
      embed: [],
      rerank: []
    }
    scenes.value = []
    loading.value = false
    activeGroup.value = 'llm'
  }

  return {
    // 状态
    models,
    scenes,
    loading,
    activeGroup,

    // 模型操作
    loadModels,
    saveModel,
    setDefault,
    deleteModel,
    getModelsByGroup,
    getDefaultModel,

    // 场景操作
    loadScenes,
    saveScene,
    deleteScene,

    // 重置
    reset
  }
})
