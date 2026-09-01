<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSettingsStore } from '@/stores/settings'
import SceneConfigDialog from './SceneConfigDialog.vue'
import type { Scene } from '@/types/settings'

const settingsStore = useSettingsStore()

const dialogVisible = ref(false)
const editingScene = ref<Scene | null>(null)

const scenes = computed(() => settingsStore.scenes)

function handleCreate() {
  editingScene.value = {
    id: '',
    name: '',
    description: '',
    config: {
      chunk_size: 512,
      top_k: 5,
      system_prompt: ''
    }
  }
  dialogVisible.value = true
}

function handleEdit(scene: Scene) {
  editingScene.value = { ...scene }
  dialogVisible.value = true
}

async function handleDelete(scene: Scene) {
  try {
    await ElMessageBox.confirm(
      `确定要删除场景 "${scene.name}" 吗？此操作不可恢复。`,
      '删除场景',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    await settingsStore.deleteScene(scene.id)
    ElMessage.success('删除成功')
  } catch (error) {
    // 用户取消删除
  }
}

async function handleSubmit(scene: Scene) {
  try {
    if (editingScene.value?.id) {
      // 更新现有场景
      await settingsStore.saveScene(scene)
      ElMessage.success('更新成功')
    } else {
      // 创建新场景
      const newScene = {
        ...scene,
        id: 'scene' + Date.now()
      }
      await settingsStore.saveScene(newScene)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
  } catch (error) {
    ElMessage.error('操作失败')
  }
}
</script>

<template>
  <div class="scene-panel">
    <div class="panel-header">
      <div class="header-info">
        <h3>场景预设管理</h3>
        <p class="description">配置不同场景下的参数预设，优化知识库检索效果</p>
      </div>
      <el-button type="primary" icon="Plus" @click="handleCreate">
        新建场景
      </el-button>
    </div>

    <div v-if="settingsStore.loading" class="loading-state">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <el-empty
      v-else-if="scenes.length === 0"
      description="暂无场景预设"
      :image-size="120"
    />

    <div v-else class="scenes-grid">
      <div
        v-for="scene in scenes"
        :key="scene.id"
        class="scene-card"
      >
        <div class="card-header">
          <h4>{{ scene.name }}</h4>
          <div class="card-actions">
            <el-button type="primary" size="small" link @click="handleEdit(scene)">
              编辑
            </el-button>
            <el-button type="danger" size="small" link @click="handleDelete(scene)">
              删除
            </el-button>
          </div>
        </div>
        <p class="card-description">{{ scene.description }}</p>
        <div class="card-params">
          <div class="param-item">
            <span class="param-label">分块大小:</span>
            <span class="param-value">{{ scene.config?.chunk_size ?? 512 }}</span>
          </div>
          <div class="param-item">
            <span class="param-label">召回数量:</span>
            <span class="param-value">{{ scene.config?.top_k ?? 5 }}</span>
          </div>
        </div>
        <div class="card-prompt">
          <div class="prompt-label">系统提示词:</div>
          <div class="prompt-content">{{ scene.config?.system_prompt ?? '' }}</div>
        </div>
      </div>
    </div>

    <SceneConfigDialog
      v-model:visible="dialogVisible"
      :data="editingScene"
      @submit="handleSubmit"
    />
  </div>
</template>

<style lang="scss" scoped>
.scene-panel {
  width: 100%;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e4e7ed;
}

.header-info {
  flex: 1;
}

.header-info h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.description {
  margin: 0;
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: #909399;

  p {
    margin-top: 12px;
  }
}

.scenes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.scene-card {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
  background: #fff;
  transition: all 0.3s ease;

  &:hover {
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    border-color: #409eff;
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;

  h4 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: #303133;
  }

  .card-actions {
    display: flex;
    gap: 8px;
  }
}

.card-description {
  margin: 0 0 12px 0;
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}

.card-params {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  padding: 8px 0;
  border-top: 1px solid #f0f0f0;
  border-bottom: 1px solid #f0f0f0;
}

.param-item {
  display: flex;
  align-items: center;
  font-size: 12px;

  .param-label {
    color: #909399;
    margin-right: 4px;
  }

  .param-value {
    color: #409eff;
    font-weight: 600;
  }
}

.card-prompt {
  margin-top: 8px;
}

.prompt-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.prompt-content {
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
  max-height: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}
</style>

