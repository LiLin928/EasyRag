# 工作流节点保存问题分析

## 问题现象
用户创建工作流后点击修改节点配置，设计的流程节点都没有保存。

## 根因分析

### 当前保存流程
1. 用户在节点配置弹窗中修改配置
2. 点击"保存"按钮
3. 触发 `NodeConfigModal.handleSave()`
4. emit('save', updatedNode) 到父组件
5. 父组件调用 `handleNodeSave(node)`
6. **只调用 `store.updateNode(node.id, node)` 更新内存**
7. **没有调用 `store.save()` 持久化到后端**

### 问题代码
```typescript
// frontend/src/views/workflow/WorkflowEditorView.vue
function handleNodeSave(node: WfNode) {
  store.updateNode(node.id, node)  // ← 只更新内存，未持久化
}
```

## 解决方案

### 方案 1：自动保存（推荐）
修改 `handleNodeSave`，自动保存到后端：

```typescript
async function handleNodeSave(node: WfNode) {
  store.updateNode(node.id, node)
  store.markDirty()  // 标记为脏数据

  // 自动保存到后端
  if (store.id) {
    try {
      await store.save()
      ElMessage.success('节点配置已保存')
    } catch (error) {
      ElMessage.error('保存失败')
    }
  }
}
```

### 方案 2：手动保存提示
在节点配置保存后，提示用户点击顶部保存按钮：

```typescript
function handleNodeSave(node: WfNode) {
  store.updateNode(node.id, node)
  store.markDirty()
  ElMessage.info('节点已更新，请点击顶部"保存"按钮保存工作流')
}
```

### 方案 3：防抖自动保存
使用防抖机制，避免频繁保存：

```typescript
import { debounce } from 'lodash-es'

const autoSave = debounce(async () => {
  if (store.id && store.dirty) {
    try {
      await store.save()
      console.log('Auto saved')
    } catch (error) {
      console.error('Auto save failed:', error)
    }
  }
}, 2000)  // 2秒后自动保存

function handleNodeSave(node: WfNode) {
  store.updateNode(node.id, node)
  store.markDirty()
  autoSave()  // 触发自动保存
}
```

## 推荐方案

**方案 1（自动保存）**最适合用户体验，节点配置修改后立即保存。

## 其他发现

### 当前工作流编辑器的保存机制
- ✅ 顶部有"保存"按钮
- ✅ store 有 `dirty` 标志追踪修改
- ❌ 节点配置修改后未自动保存
- ❌ 没有离开页面时的保存提示

### 建议改进
1. 节点配置修改后自动保存
2. 离开页面时提示保存（如果 dirty 为 true）
3. 添加保存状态指示器
4. 支持撤销操作（已有 undo 功能）