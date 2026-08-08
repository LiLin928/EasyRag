import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as kbApi from '@/api/knowledge'
import type { KnowledgeBase, Document, TreeNode, DocElement, ParseTask } from '@/types/knowledge'

export const useKnowledgeStore = defineStore('knowledge', () => {
  // ========== 知识库状态 ==========
  const kbList = ref<KnowledgeBase[]>([])
  const currentKb = ref<KnowledgeBase | null>(null)
  const kbLoading = ref(false)

  // ========== 文档状态 ==========
  const docList = ref<Document[]>([])
  const currentDoc = ref<Document | null>(null)
  const docTotal = ref(0)
  const docLoading = ref(false)

  // ========== 结构树与元素 ==========
  const tree = ref<TreeNode[]>([])
  const elements = ref<DocElement[]>([])
  const elementTotal = ref(0)

  // ========== 上传队列 ==========
  const uploadQueue = ref<ParseTask[]>([])

  // ========== 知识库操作 ==========
  
  async function loadKbList(keyword?: string) {
    kbLoading.value = true
    try {
      kbList.value = await kbApi.getKbList({ keyword })
    } finally {
      kbLoading.value = false
    }
  }

  async function createKb(data: Partial<KnowledgeBase>) {
    const kb = await kbApi.createKb(data)
    kbList.value.unshift(kb)
    return kb
  }

  async function updateKb(id: string, data: Partial<KnowledgeBase>) {
    const kb = await kbApi.updateKb(id, data)
    const index = kbList.value.findIndex(k => k.id === id)
    if (index > -1) {
      kbList.value[index] = kb
    }
    return kb
  }

  async function deleteKb(id: string) {
    await kbApi.deleteKb(id)
    kbList.value = kbList.value.filter(k => k.id !== id)
  }

  async function loadKbDetail(id: string) {
    currentKb.value = await kbApi.getKbDetail(id)
  }

  // ========== 文档操作 ==========

  async function loadDocuments(kbId: string, page = 1, pageSize = 20) {
    docLoading.value = true
    try {
      const result = await kbApi.getDocumentList({ kb_id: kbId, page, pageSize })
      docList.value = result.list
      docTotal.value = result.total
    } finally {
      docLoading.value = false
    }
  }

  async function uploadFiles(kbId: string, files: File[], mode: 'fast' | 'precision', scene?: string) {
    const tasks: ParseTask[] = []
    
    for (const file of files) {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('kbId', kbId)
      formData.append('mode', mode)
      if (scene) formData.append('scene', scene)
      
      const result = await kbApi.uploadDocument(formData)
      tasks.push({
        task_id: result.task_id,
        doc_id: result.doc_id,
        status: 'pending',
        pct: 0
      })
    }
    
    uploadQueue.value.push(...tasks)
    return tasks
  }

  async function deleteDocument(id: string) {
    await kbApi.deleteDocument(id)
    docList.value = docList.value.filter(d => d.id !== id)
  }

  // ========== 解析任务轮询 ==========

  function startPolling(taskId: string, onComplete?: () => void) {
    const poll = async () => {
      try {
        const task = await kbApi.getParseTask(taskId)
        const index = uploadQueue.value.findIndex(t => t.task_id === taskId)
        if (index > -1) {
          uploadQueue.value[index] = task
        }
        
        if (task.status === 'done' || task.status === 'failed') {
          if (onComplete) onComplete()
          return
        }
        
        // 继续轮询
        setTimeout(poll, 2000)
      } catch (error) {
        console.error('Poll task error:', error)
      }
    }
    
    poll()
  }

  // ========== 结构树与元素 ==========

  async function loadTree(docId: string) {
    tree.value = await kbApi.getDocTree(docId)
  }

  async function loadElements(docId: string, params: { nodeId?: string; type?: string; page?: number; pageSize?: number } = {}) {
    const result = await kbApi.getDocElements({ docId, ...params })
    elements.value = result.list
    elementTotal.value = result.total
  }

  // ========== 重置状态 ==========

  function reset() {
    kbList.value = []
    currentKb.value = null
    docList.value = []
    currentDoc.value = null
    docTotal.value = 0
    tree.value = []
    elements.value = []
    elementTotal.value = 0
    uploadQueue.value = []
  }

  return {
    // 状态
    kbList,
    currentKb,
    kbLoading,
    docList,
    currentDoc,
    docTotal,
    docLoading,
    tree,
    elements,
    elementTotal,
    uploadQueue,
    
    // 知识库操作
    loadKbList,
    createKb,
    updateKb,
    deleteKb,
    loadKbDetail,
    
    // 文档操作
    loadDocuments,
    uploadFiles,
    deleteDocument,
    
    // 解析任务
    startPolling,
    
    // 结构树与元素
    loadTree,
    loadElements,
    
    // 重置
    reset
  }
})
