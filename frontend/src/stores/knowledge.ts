import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as kbApi from '@/api/knowledge'
import type {
  ChunkAsset,
  DocElement,
  Document,
  KnowledgeBase,
  MetadataField,
  MetadataFieldPayload,
  MetadataScope,
  ParseTask,
  RetrievalRunPayload,
  RetrievalSettings,
  RetrievalSettingsPayload,
  RetrievalTestCase,
  RetrievalTestCasePayload,
  RetrievalTestCaseResult,
  RetrievalTestRun,
  RetrievalTestSet,
  RetrievalTestSetPayload,
  TreeNode,
} from '@/types/knowledge'

type KnowledgeTab = 'documents' | 'segments' | 'metadata' | 'testing' | 'settings'
type Filter = Record<string, unknown>

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
  const documentFilter = ref<Filter>({})

  // ========== 分段状态 ==========
  const chunkList = ref<ChunkAsset[]>([])
  const chunkTotal = ref(0)
  const chunkLoading = ref(false)
  const chunkFilter = ref<Filter>({})

  // ========== 元数据与检索配置 ==========
  const metadataFields = ref<MetadataField[]>([])
  const retrievalSettings = ref<RetrievalSettings | null>(null)

  // ========== 召回测试状态 ==========
  const testSets = ref<RetrievalTestSet[]>([])
  const currentTestSet = ref<RetrievalTestSet | null>(null)
  const testCases = ref<RetrievalTestCase[]>([])
  const currentRun = ref<RetrievalTestRun | null>(null)
  const runResults = ref<RetrievalTestCaseResult[]>([])
  const activeTab = ref<KnowledgeTab>('documents')

  // ========== 结构树与元素 ==========
  const tree = ref<TreeNode[]>([])
  const elements = ref<DocElement[]>([])
  const elementTotal = ref(0)

  // ========== 上传队列 ==========
  const uploadQueue = ref<ParseTask[]>([])

  let runPollTimer: ReturnType<typeof setInterval> | null = null

  function isTerminalRun(run: RetrievalTestRun | null): boolean {
    return run?.status === 'completed' || run?.status === 'failed' || run?.status === 'canceled'
  }

  function stopRunPolling(): void {
    if (runPollTimer !== null) {
      clearInterval(runPollTimer)
      runPollTimer = null
    }
  }

  async function refreshRun(runId: string): Promise<RetrievalTestRun> {
    const run = await kbApi.getTestRun(runId)
    currentRun.value = run
    if (isTerminalRun(run)) stopRunPolling()
    return run
  }

  // ========== 知识库操作 ==========
  async function loadKbList(keyword?: string): Promise<void> {
    kbLoading.value = true
    try {
      kbList.value = await kbApi.getKbList({ keyword })
    } finally {
      kbLoading.value = false
    }
  }

  async function createKb(data: Partial<KnowledgeBase>): Promise<KnowledgeBase> {
    const kb = await kbApi.createKb(data)
    kbList.value.unshift(kb)
    return kb
  }

  async function updateKb(id: string, data: Partial<KnowledgeBase>): Promise<KnowledgeBase> {
    const kb = await kbApi.updateKb(id, data)
    const index = kbList.value.findIndex((item) => item.id === id)
    if (index > -1) kbList.value[index] = kb
    if (currentKb.value?.id === id) currentKb.value = kb
    return kb
  }

  async function deleteKb(id: string): Promise<void> {
    await kbApi.deleteKb(id)
    kbList.value = kbList.value.filter((item) => item.id !== id)
    if (currentKb.value?.id === id) currentKb.value = null
  }

  async function loadKbDetail(id: string): Promise<void> {
    currentKb.value = await kbApi.getKbDetail(id)
  }

  // ========== 文档操作 ==========
  async function loadDocuments(
    kbId: string,
    page = 1,
    pageSize = 20,
    filter: Filter = {}
  ): Promise<void> {
    docLoading.value = true
    documentFilter.value = filter
    try {
      const result = await kbApi.getDocumentList({
        ...filter,
        kb_id: kbId,
        page,
        page_size: pageSize
      })
      docList.value = result.list
      docTotal.value = result.total
    } finally {
      docLoading.value = false
    }
  }

  async function uploadFiles(
    kbId: string,
    files: File[],
    mode: 'fast' | 'precision',
    scene?: string
  ): Promise<ParseTask[]> {
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

  async function deleteDocument(id: string): Promise<void> {
    await kbApi.deleteDocument(id)
    docList.value = docList.value.filter((item) => item.id !== id)
    docTotal.value = Math.max(0, docTotal.value - 1)
  }

  // ========== 解析任务轮询 ==========
  function startPolling(taskId: string, onComplete?: () => void): void {
    const poll = async (): Promise<void> => {
      try {
        const task = await kbApi.getParseTask(taskId)
        const index = uploadQueue.value.findIndex((item) => item.task_id === taskId)
        if (index > -1) uploadQueue.value[index] = task
        if (task.status === 'done' || task.status === 'failed') {
          onComplete?.()
          return
        }
        setTimeout(poll, 2000)
      } catch (error) {
        console.error('Poll task error:', error)
      }
    }

    void poll()
  }

  // ========== 元数据 Schema ==========
  async function loadMetadataFields(kbId: string, scope?: MetadataScope): Promise<void> {
    metadataFields.value = await kbApi.getMetadataFields(kbId, scope)
  }

  async function saveMetadataField(
    kbId: string,
    payload: MetadataFieldPayload,
    id?: string
  ): Promise<MetadataField> {
    const field = id
      ? await kbApi.updateMetadataField(kbId, id, payload)
      : await kbApi.createMetadataField(kbId, payload)
    const index = metadataFields.value.findIndex((item) => item.id === field.id)
    if (index > -1) metadataFields.value[index] = field
    else metadataFields.value.push(field)
    return field
  }

  async function removeMetadataField(
    kbId: string,
    id: string,
    force: boolean
  ): Promise<{ success: boolean; affected_count: number }> {
    const impact = await kbApi.deleteMetadataField(kbId, id, force)
    if (impact.success) {
      metadataFields.value = metadataFields.value.filter((item) => item.id !== id)
    }
    return impact
  }

  async function saveDocumentMetadata(
    ids: string[],
    metadata: Filter
  ): Promise<void> {
    if (ids.length === 1) {
      const document = await kbApi.updateDocumentMetadata(ids[0], metadata)
      const index = docList.value.findIndex((item) => item.id === document.id)
      if (index > -1) docList.value[index] = document
      return
    }
    await kbApi.batchUpdateDocumentMetadata(ids, metadata)
    docList.value = docList.value.map((item) =>
      ids.includes(item.id) ? { ...item, metadata: { ...item.metadata, ...metadata } } : item
    )
  }

  async function setDocumentEnabled(ids: string[], enabled: boolean): Promise<void> {
    await kbApi.updateDocumentStatus(ids, enabled)
    docList.value = docList.value.map((item) =>
      ids.includes(item.id) ? { ...item, enabled } : item
    )
  }

  // ========== 分段操作 ==========
  async function loadChunks(kbId: string, filter: Filter = {}): Promise<void> {
    chunkLoading.value = true
    chunkFilter.value = filter
    try {
      const result = await kbApi.getChunkList({ ...filter, kb_id: kbId })
      chunkList.value = result.list
      chunkTotal.value = result.total
    } finally {
      chunkLoading.value = false
    }
  }

  async function saveChunkMetadata(ids: string[], metadata: Filter): Promise<void> {
    if (ids.length === 1) {
      const chunk = await kbApi.updateChunkMetadata(ids[0], metadata)
      const index = chunkList.value.findIndex((item) => item.id === chunk.id)
      if (index > -1) chunkList.value[index] = chunk
      return
    }
    await kbApi.batchUpdateChunkMetadata(ids, metadata)
    chunkList.value = chunkList.value.map((item) =>
      ids.includes(item.id) ? { ...item, metadata: { ...item.metadata, ...metadata } } : item
    )
  }

  async function setChunkEnabled(ids: string[], enabled: boolean): Promise<void> {
    await kbApi.updateChunkStatus(ids, enabled)
    chunkList.value = chunkList.value.map((item) =>
      ids.includes(item.id) ? { ...item, enabled } : item
    )
  }

  async function queueReembedding(
    kbId: string,
    documentIds: string[],
    chunkIds: string[]
  ): Promise<{ queued: boolean }> {
    return kbApi.reembedChunks(kbId, documentIds, chunkIds)
  }

  // ========== 检索配置 ==========
  async function loadRetrievalSettings(kbId: string): Promise<void> {
    retrievalSettings.value = await kbApi.getRetrievalSettings(kbId)
  }

  async function saveRetrievalSettings(
    kbId: string,
    payload: RetrievalSettingsPayload
  ): Promise<RetrievalSettings> {
    retrievalSettings.value = await kbApi.saveRetrievalSettings(kbId, payload)
    return retrievalSettings.value
  }

  // ========== 召回测试集 ==========
  async function loadTestSets(kbId: string, includeArchived?: boolean): Promise<void> {
    const result = await kbApi.getTestSets(kbId, includeArchived)
    testSets.value = result.list
  }

  async function saveTestSet(
    kbId: string,
    payload: RetrievalTestSetPayload,
    setId?: string
  ): Promise<RetrievalTestSet> {
    const testSet = setId
      ? await kbApi.updateTestSet(setId, payload)
      : await kbApi.createTestSet(kbId, payload)
    const index = testSets.value.findIndex((item) => item.id === testSet.id)
    if (index > -1) testSets.value[index] = testSet
    else testSets.value.unshift(testSet)
    currentTestSet.value = testSet
    return testSet
  }

  async function removeTestSet(setId: string): Promise<void> {
    await kbApi.deleteTestSet(setId)
    testSets.value = testSets.value.filter((item) => item.id !== setId)
    if (currentTestSet.value?.id === setId) {
      currentTestSet.value = null
      testCases.value = []
      currentRun.value = null
      runResults.value = []
      stopRunPolling()
    }
  }

  // ========== 召回测试用例 ==========
  async function loadTestCases(setId: string): Promise<void> {
    const result = await kbApi.getTestCases(setId)
    testCases.value = result.list
  }

  async function saveTestCase(
    setId: string,
    payload: RetrievalTestCasePayload,
    caseId?: string
  ): Promise<RetrievalTestCase> {
    const testCase = caseId
      ? await kbApi.updateTestCase(caseId, payload)
      : await kbApi.createTestCase(setId, payload)
    const index = testCases.value.findIndex((item) => item.id === testCase.id)
    if (index > -1) testCases.value[index] = testCase
    else testCases.value.push(testCase)
    return testCase
  }

  async function removeTestCase(caseId: string): Promise<void> {
    await kbApi.deleteTestCase(caseId)
    testCases.value = testCases.value.filter((item) => item.id !== caseId)
  }

  async function setTestCaseEnabled(ids: string[], enabled: boolean): Promise<void> {
    await kbApi.updateTestCaseStatus(ids, enabled)
    testCases.value = testCases.value.map((item) =>
      ids.includes(item.id) ? { ...item, enabled } : item
    )
  }

  // ========== 测试运行 ==========
  async function startTestRun(
    setId: string,
    payload: RetrievalRunPayload
  ): Promise<RetrievalTestRun> {
    stopRunPolling()
    currentRun.value = await kbApi.startTestRun(setId, payload)
    runResults.value = []
    if (!isTerminalRun(currentRun.value)) await pollTestRun(currentRun.value.id)
    return currentRun.value
  }

  async function pollTestRun(runId: string): Promise<void> {
    if (runPollTimer !== null && currentRun.value?.id === runId) return
    if (runPollTimer !== null) stopRunPolling()

    await refreshRun(runId)
    if (isTerminalRun(currentRun.value)) return
    if (runPollTimer !== null) return

    runPollTimer = setInterval(() => {
      void refreshRun(runId).catch((error: unknown) => {
        console.error('Poll retrieval test run error:', error)
      })
    }, 2000)
  }

  async function cancelTestRun(runId: string): Promise<RetrievalTestRun> {
    stopRunPolling()
    currentRun.value = await kbApi.cancelTestRun(runId)
    return currentRun.value
  }

  async function loadRunResults(runId: string): Promise<void> {
    const result = await kbApi.getTestRunResults(runId)
    runResults.value = result.list
  }

  // ========== 结构树与元素 ==========
  async function loadTree(docId: string): Promise<void> {
    tree.value = await kbApi.getDocTree(docId)
  }

  async function loadElements(
    docId: string,
    params: { nodeId?: string; type?: string; page?: number; pageSize?: number } = {}
  ): Promise<void> {
    const result = await kbApi.getDocElements({ docId, ...params })
    elements.value = result.list
    elementTotal.value = result.total
  }

  // ========== 重置状态 ==========
  function reset(): void {
    stopRunPolling()
    kbList.value = []
    currentKb.value = null
    docList.value = []
    currentDoc.value = null
    docTotal.value = 0
    documentFilter.value = {}
    chunkList.value = []
    chunkTotal.value = 0
    chunkLoading.value = false
    chunkFilter.value = {}
    metadataFields.value = []
    retrievalSettings.value = null
    testSets.value = []
    currentTestSet.value = null
    testCases.value = []
    currentRun.value = null
    runResults.value = []
    activeTab.value = 'documents'
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
    documentFilter,
    chunkList,
    chunkTotal,
    chunkLoading,
    chunkFilter,
    metadataFields,
    retrievalSettings,
    testSets,
    currentTestSet,
    testCases,
    currentRun,
    runResults,
    activeTab,
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
    saveDocumentMetadata,
    setDocumentEnabled,

    // 解析任务
    startPolling,

    // 元数据操作
    loadMetadataFields,
    saveMetadataField,
    removeMetadataField,

    // 分段操作
    loadChunks,
    saveChunkMetadata,
    setChunkEnabled,
    queueReembedding,

    // 检索配置
    loadRetrievalSettings,
    saveRetrievalSettings,

    // 召回测试
    loadTestSets,
    saveTestSet,
    removeTestSet,
    loadTestCases,
    saveTestCase,
    removeTestCase,
    setTestCaseEnabled,
    startTestRun,
    pollTestRun,
    cancelTestRun,
    loadRunResults,

    // 结构树与元素
    loadTree,
    loadElements,

    // 重置
    reset
  }
})
