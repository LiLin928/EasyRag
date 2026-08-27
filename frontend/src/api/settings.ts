// 系统设置 API
import request from './request'
import type { ModelGroup, ModelDef, Scene } from '@/types/settings'

// ========== 模型配置 ==========

export function getModels(): Promise<Record<ModelGroup, ModelDef[]>> {
  return request.get('/settings/models')
}

export function getModelsByGroup(group: ModelGroup): Promise<ModelDef[]> {
  return request.get('/settings/models?group=' + group)
}

export function saveModel(group: ModelGroup, model: ModelDef): Promise<ModelDef> {
  return request.post('/settings/models?group=' + group, model)
}

export function setDefault(group: ModelGroup, name: string): Promise<{ success: boolean }> {
  return request.put('/settings/models/' + group + '/default?name=' + name)
}

export function deleteModel(group: ModelGroup, name: string): Promise<{ success: boolean }> {
  return request.delete('/settings/models?group=' + group + '&name=' + name)
}

// ========== 场景预设 ==========

export function getScenes(): Promise<Scene[]> {
  return request.get('/settings/scenes')
}

export function getScene(id: string): Promise<Scene> {
  return request.get('/settings/scenes/' + id)
}

export function saveScene(scene: Scene): Promise<Scene> {
  if (scene.id.startsWith('scene')) {
    return request.put('/settings/scenes/' + scene.id, scene)
  } else {
    return request.post('/settings/scenes', scene)
  }
}

export function deleteScene(id: string): Promise<{ success: boolean }> {
  return request.delete('/settings/scenes/' + id)
}
