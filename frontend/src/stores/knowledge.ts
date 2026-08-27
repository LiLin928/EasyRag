import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as kbApi from '@/api/knowledge'
import type {
  KnowledgeBase, Document, TreeNode, DocElement, ParseTask,
  RetrievalSettings, MetadataField, Segment, HitTestResult, HitTestRecord,
  RetrievalTestSet, RetrievalTestCase, RetrievalTestRun
} from '@/types/knowledge'

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

  // ========== 检索设置 ==========
  const retrievalSettings = ref<RetrievalSettings | null>(null)

  // ========== 元数据字段 ==========
  const metadataFields = ref<MetadataField[]>([])

  // ========== 分段 ==========
  const segments = ref<Segment[]>([])
  const segmentTotal = ref(0)

  // ========== 召回测试 ==========
  const hitTestResult = ref<HitTestResult | null>(null)
  const hitTestRecords = ref<HitTestRecord[]>([])
  const testSets = ref<RetrievalTestSet[]>([])
  const testCases = ref<RetrievalTestCase[]>([])
  const testRun = ref<RetrievalTestRun | null>(null)

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

  // ========== 检索设置 ==========

  async function loadRetrievalSettings(kbId: string) {
    retrievalSettings.value = await kbApi.getRetrievalSettings(kbId)
  }

  async function saveRetrievalSettings(kbId: string, data: Partial<RetrievalSettings>) {
    retrievalSettings.value = await kbApi.updateRetrievalSettings(kbId, data)
  }

  // ========== 元数据字段 ==========

  async function loadMetadataFields(kbId: string) {
    metadataFields.value = await kbApi.getMetadataFields(kbId)
  }

  async function createMetadataField(kbId: string, data: Partial<MetadataField>) {
    const field = await kbApi.createMetadataField(kbId, data)
    metadataFields.value.push(field)
    return field
  }

  async function updateMetadataField(fieldId: string, data: Partial<MetadataField>) {
    const field = await kbApi.updateMetadataField(fieldId, data)
    const index = metadataFields.value.findIndex(f => f.id === fieldId)
    if (index > -1) {
      metadataFields.value[index] = field
    }
    return field
  }

  async function deleteMetadataField(fieldId: string) {
    await kbApi.deleteMetadataField(fieldId)
    metadataFields.value = metadataFields.value.filter(f => f.id !== fieldId)
  }

  // ========== 分段 ==========

  async function loadSegments(kbId: string, params?: { docId?: string; page?: number; pageSize?: number }) {
    const result = await kbApi.getSegments(kbId, params)
    segments.value = result.list
    segmentTotal.value = result.total
  }

  async function updateSegmentMetadata(segmentId: string, data: Record<string, string>) {
    await kbApi.updateSegmentMetadata(segmentId, data)
    const seg = findSegment(segments.value, segmentId)
    if (seg) {
      seg.metadata = { ...seg.metadata, ...data }
    }
  }

  async function updateSegmentStatus(segmentId: string, enabled: boolean) {
    await kbApi.updateSegmentStatus(segmentId, enabled)
    const seg = findSegment(segments.value, segmentId)
    if (seg) {
      seg.enabled = enabled
    }
  }

  function findSegment(list: Segment[], id: string): Segment | undefined {
    for (const seg of list) {
      if (seg.id === id) return seg
      if (seg.children) {
        const child = findSegment(seg.children, id)
        if (child) return child
      }
    }
    return undefined
  }

  // ========== 召回测试（即时） ==========

  async function runHitTest(kbId: string, query: string) {
    hitTestResult.value = await kbApi.hitTest(kbId, query)
    return hitTestResult.value
  }

  async function loadHitTestRecords(kbId: string) {
    hitTestRecords.value = await kbApi.getHitTestRecords(kbId)
  }

  // ========== 召回测试（批量） ==========

  async function loadTestSets(kbId: string) {
    testSets.value = await kbApi.getTestSets(kbId)
  }

  async function createTestSet(kbId: string, data: Partial<RetrievalTestSet>) {
    const ts = await kbApi.createTestSet(kbId, data)
    testSets.value.unshift(ts)
    return ts
  }

  async function loadTestCases(testSetId: string) {
    testCases.value = await kbApi.getTestCases(testSetId)
  }

  async function createTestCase(testSetId: string, data: Partial<RetrievalTestCase>) {
    const tc = await kbApi.createTestCase(testSetId, data)
    testCases.value.push(tc)
    return tc
  }

  async function updateTestCase(caseId: string, data: Partial<RetrievalTestCase>) {
    const tc = await kbApi.updateTestCase(caseId, data)
    const index = testCases.value.findIndex(c => c.id === caseId)
    if (index > -1) {
      testCases.value[index] = tc
    }
    return tc
  }

  async function deleteTestCase(caseId: string) {
    await kbApi.deleteTestCase(caseId)
    testCases.value = testCases.value.filter(c => c.id !== caseId)
  }

  async function runTestRun(testSetId: string, kbId: string) {
    testRun.value = await kbApi.createTestRun(testSetId, { kbId })
    return testRun.value
  }

  async function loadTestRun(runId: string) {
    testRun.value = await kbApi.getTestRun(runId)
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
    retrievalSettings.value = null
    metadataFields.value = []
    segments.value = []
    segmentTotal.value = 0
    hitTestResult.value = null
    hitTestRecords.value = []
    testSets.value = []
    testCases.value = []
    testRun.value = null
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
    retrievalSettings,
    metadataFields,
    segments,
    segmentTotal,
    hitTestResult,
    hitTestRecords,
    testSets,
    testCases,
    testRun,
    
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
    
    // 检索设置
    loadRetrievalSettings,
    saveRetrievalSettings,

    // 元数据字段
    loadMetadataFields,
    createMetadataField,
    updateMetadataField,
    deleteMetadataField,

    // 分段
    loadSegments,
    updateSegmentMetadata,
    updateSegmentStatus,

    // 召回测试
    runHitTest,
    loadHitTestRecords,
    loadTestSets,
    createTestSet,
    loadTestCases,
    createTestCase,
    updateTestCase,
    deleteTestCase,
    runTestRun,
    loadTestRun,

    // 重置
    reset
  }
})
