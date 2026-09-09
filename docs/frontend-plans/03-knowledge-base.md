# 03 · 知识库管理 Knowledge Base（列表 + 五 Tab 详情 + 文档详情）

> 原型页面：page-documents + page-doc-detail。
> 知识库详情升级为五标签页管理闭环：文档 / 分段 / 元数据 / 召回测试 / 设置。

## 1. 目标

**知识库列表 → 知识库详情（五 Tab）→ 文档详情（结构树 + 元素浏览）**。

知识库详情包含五个标签页：

1. **文档** — 文档上传、筛选、元数据、启停、批量操作
2. **分段** — 分段列表、结构树导航、元数据维护、向量化状态
3. **元数据** — 双作用域（document / chunk）字段 Schema 管理
4. **召回测试** — 测试集 CRUD、用例标注、异步批量运行、指标面板
5. **设置** — 知识库级 Embedding / Rerank / 检索参数配置

上传文档时必须归属某个知识库；对话的文档选择基于知识库。

## 2. 数据模型（类型 types/knowledge.ts）

```ts
// 知识库
interface KnowledgeBase {
  id: string; name: string; description: string | null; scene: string;
  cover: string | null; doc_count: number; total_size: number;
  chunk_count: number; last_test_at: string | null; created_at: string;
}

// 元数据字段
type MetadataScope = 'document' | 'chunk'
type MetadataDataType = 'string' | 'number' | 'date' | 'select' | 'boolean'
interface MetadataField {
  id: string; kb_id: string; key: string; name: string; scope: MetadataScope;
  data_type: MetadataDataType; options: string[]; default_value: unknown;
  required: boolean; filterable: boolean; retrieval_filterable: boolean;
  visible: boolean; built_in: boolean; mapped_field: string | null; sort_order: number;
}

// 文档资产（含元数据、启停、召回统计）
interface DocumentAsset {
  id: string; kb_id: string; name: string; ext: string; size: number; pages: number;
  mode: 'fast' | 'precision'; status: 'pending' | 'parsing' | 'done' | 'failed';
  pct: number; element_count: number; chunk_count: number;
  metadata: Record<string, unknown>; enabled: boolean; recall_count: number; created_at: string;
}

// 分段资产（含元数据、启停、召回统计、向量状态）
interface ChunkAsset {
  id: string; kb_id: string; document_id: string; document_name: string;
  content: string; content_search: string | null; clause_title: string | null;
  section_path: string | null; page_number: number; seq: number; char_count: number;
  embedding_model: string | null; metadata: Record<string, unknown>;
  enabled: boolean; recall_count: number; created_at: string;
}

// 检索配置
interface ConfigSource { value: string | number | boolean; source: 'override' | 'knowledge_base' | 'scene' | 'system_default' }
interface RetrievalSettings {
  values: Record<string, ConfigSource>; resolved: Record<string, string | number | boolean>;
  embedding_model: { id: string; name: string; prov: string; params: Record<string, unknown> } | null;
  rerank_model: { id: string; name: string; prov: string } | null;
  rebuild_required: boolean;
}

// 召回测试
type TestRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'canceled'
interface RetrievalTestSet { id: string; kb_id: string; name: string; description: string | null; archived: boolean; case_count: number; last_run_at: string | null; last_metrics: Record<string, Record<string, number | null>> | null; created_at: string; updated_at: string }
interface RetrievalTestCase { id: string; test_set_id: string; query: string; expected_doc_ids: string[]; expected_chunk_ids: string[]; tags: string[]; enabled: boolean; sort_order: number; first_expected_hit_rank?: number | null; status?: TestCaseStatus; latency_ms?: number | null; last_run_at?: string | null; created_at: string; updated_at: string }
interface RetrievalTestRun { id: string; test_set_id: string; kb_id: string; status: TestRunStatus; config_snapshot: {...}; override_config: Record<string, unknown>; total_cases: number; completed_cases: number; metrics: Record<string, Record<string, number | null> | number | null>; error: string | null; started_at: string | null; finished_at: string | null; created_at: string }
interface RetrievalCandidate { rank: number; chunk_id: string; document_id: string; document_name: string; section_path: string | null; page_number: number; char_count: number; vector_score: number | null; keyword_score: number | null; vector_rank: number | null; keyword_rank: number | null; rrf_score: number | null; rerank_score: number | null; metadata: Record<string, unknown> }
interface RetrievalTestCaseResult extends RetrievalTestCase { run_id: string; hit_doc_ids: string[]; results: RetrievalCandidate[]; metrics: Record<string, unknown>; error: string | null }

// 结构树与元素
interface TreeNode { node_id: string; title: string; level: number; summary?: string | null; element_count: number; children: TreeNode[] }
interface DocElement { element_id: string; doc_title: string; type: 'text' | 'table' | 'image' | 'heading'; content: string; node_id: string; node_title: string; page_number: number; seq: number; prev_element_id?: string; next_element_id?: string }
```

## 3. 路由

```
/knowledge                       KnowledgeListView    知识库卡片网格
/knowledge/:kbId                 KbDetailView         知识库详情（五 Tab）
/knowledge/:kbId/docs/:docId     DocDetailView        文档详情（结构树 + 元素）
```

## 4. 知识库列表页（KnowledgeListView）

三栏式卡片网格（每卡片：封面色块 + 名称 + 文档数 + 大小 + 场景标签）。右上「新建知识库」按钮。

| 组件 | 路径 | 职责 |
|------|------|------|
| KnowledgeListView | views/knowledge/KnowledgeListView.vue | 页面容器 + 搜索 + 卡片网格 + 空态 |
| KbCard | views/knowledge/components/KbCard.vue | 单卡片：点击进详情；右上菜单（编辑/删除） |
| KbFormDialog | views/knowledge/components/KbFormDialog.vue | 新建/编辑弹窗：名称/描述/场景选择 |

## 5. 知识库详情（KbDetailView — 五 Tab）

顶部：知识库页头（名称 + 描述 + 文档数 + 分段数 + 最近测试时间 + 上传/运行快捷按钮）。下方 el-tabs 切换五个面板。

| 组件 | 路径 | 职责 |
|------|------|------|
| KbDetailView | views/knowledge/KbDetailView.vue | 五 Tab 容器：页头 + el-tabs 路由同步 + KB 加载 |
| DocumentsTab | views/knowledge/components/DocumentsTab.vue | 文档 Tab：筛选栏 + DocumentTable + UploadPanel |
| SegmentsTab | views/knowledge/components/SegmentsTab.vue | 分段 Tab：左侧结构树 + 分段筛选 + 表格 + 底部详情面板 |
| MetadataTab | views/knowledge/components/MetadataTab.vue | 元数据 Tab：双作用域字段表格 + MetadataFieldDialog + 删除确认 |
| RetrievalTestingTab | views/knowledge/components/RetrievalTestingTab.vue | 召回测试 Tab：TestSetList + TestCaseTable + TestRunPanel |
| RetrievalSettingsTab | views/knowledge/components/RetrievalSettingsTab.vue | 设置 Tab：来源标签配置 + 模型绑定 + 权重滑块 + 重建提示 |

### 文档 Tab 子组件

| 组件 | 路径 | 职责 |
|------|------|------|
| DocumentTable | views/knowledge/components/DocumentTable.vue | 文档列表表格：名/大小/状态/分段数/召回次数/元数据标签/启停/操作；批量元数据与启停 |
| UploadPanel | views/knowledge/components/UploadPanel.vue | el-upload 拖拽区 + 解析模式 + 场景；上传后轮询状态 |
| MetadataEditor | views/knowledge/components/MetadataEditor.vue | 通用元数据编辑面板（文档/分段共用），按 schema 动态渲染字段 |

### 元数据 Tab 子组件

| 组件 | 路径 | 职责 |
|------|------|------|
| MetadataFieldDialog | views/knowledge/components/MetadataFieldDialog.vue | 新建/编辑元数据字段弹窗：标识/名称/作用域/类型/选项/必填/筛选/检索/展示 |

### 召回测试 Tab 子组件

| 组件 | 路径 | 职责 |
|------|------|------|
| TestSetList | views/knowledge/components/TestSetList.vue | 测试集列表：新建/编辑/归档/删除；选中加载用例 |
| TestCaseTable | views/knowledge/components/TestCaseTable.vue | 用例表格：查询/期望文档/标签/启停；TestCaseDialog 编辑 |
| TestRunPanel | views/knowledge/components/TestRunPanel.vue | 运行面板：选择用例/K/覆盖配置 → 发起运行 → 指标汇总 + 结果表 |
| TestCaseDialog | views/knowledge/components/TestCaseDialog.vue | 用例编辑弹窗：查询 + 期望文档选择 + 标签 |
| CandidateDetailDrawer | views/knowledge/components/CandidateDetailDrawer.vue | 候选详情抽屉：排名/分段/分数/元数据/期望高亮 |

**解析状态轮询**：上传返回 task_id，每 2s 轮询 `GET /parse-tasks/{id}`，更新 status/pct；完成停止轮询并刷新列表。

**测试运行轮询**：POST run 后每 2s 轮询 `GET /test-runs/{id}`；终止态（completed/failed/canceled）、路由切换、Tab 切换、KB 切换、组件卸载时停止。

## 6. 文档详情（DocDetailView）

左右分栏：左结构树 + 右元素列表（按章节分组）。结构树高亮"命中"节点（对话引用跳转用）。

| 组件 | 路径 | 职责 |
|------|------|------|
| DocDetailView | views/knowledge/docs/DocDetailView.vue | 容器：文档信息 + 树 + 元素区 |
| TreeBrowser | views/knowledge/docs/TreeBrowser.vue | el-tree 结构树（可折叠），节点显示 element_count；支持定位/高亮 |
| ElementList | views/knowledge/docs/ElementList.vue | 选中章节的元素列表；按类型渲染（text/table/image） |
| ElementCard | views/knowledge/docs/ElementCard.vue | 单元素卡：类型标签 + 内容 + 页码 + 所属章节 |

## 7. Store（stores/knowledge.ts）

```ts
state: {
  // 知识库
  kbList: KnowledgeBase[], currentKb, kbLoading,
  // 文档
  docList: Document[], currentDoc, docTotal, docLoading, documentFilter,
  // 分段
  chunkList: ChunkAsset[], chunkTotal, chunkLoading, chunkFilter,
  // 元数据与检索配置
  metadataFields: MetadataField[], retrievalSettings: RetrievalSettings | null,
  // 召回测试
  testSets: RetrievalTestSet[], currentTestSet, testCases: RetrievalTestCase[],
  currentRun: RetrievalTestRun | null, runResults: RetrievalTestCaseResult[], activeTab,
  // 结构树与元素
  tree: TreeNode[], elements: DocElement[], elementTotal,
  // 上传队列
  uploadQueue: ParseTask[]
}
actions: {
  // 知识库
  loadKbList(), createKb(), updateKb(), deleteKb(), loadKbDetail(),
  // 文档
  loadDocuments(), uploadFiles(), deleteDocument(), saveDocumentMetadata(), setDocumentEnabled(),
  // 解析
  startPolling(),
  // 元数据
  loadMetadataFields(), saveMetadataField(), updateMetadataField(), removeMetadataField(), reorderMetadataFields(),
  // 分段
  loadChunks(), saveChunkMetadata(), setChunkEnabled(), queueReembedding(),
  // 检索配置
  loadRetrievalSettings(), saveRetrievalSettings(),
  // 召回测试
  loadTestSets(), saveTestSet(), removeTestSet(), loadTestCases(), saveTestCase(), removeTestCase(),
  setTestCaseEnabled(), startTestRun(), pollTestRun(), cancelTestRun(), loadRunResults(), loadTestRuns(),
  selectTestSet(), clearRunState(), setCurrentRun(), stopRunPolling(),
  // 结构树与元素
  loadTree(), loadElements(),
  // 重置
  reset()
}
```

## 8. 接口

### 知识库 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST/PUT/DELETE | /knowledge[/:id] | 知识库 CRUD |

### 文档管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /documents/upload | 上传（带 kbId + parse_mode + scene） |
| GET | /documents?kb_id=&status=&enabled=&document_metadata= | 文档列表（分页 + 元数据过滤） |
| GET/DELETE | /documents/{id} | 文档详情/删除 |
| PATCH | /documents/{id}/metadata | 更新文档元数据 |
| POST | /documents/batch-metadata | 批量更新文档元数据 |
| POST | /documents/batch-status | 批量启停文档 |
| GET | /documents/{id}/tree | 结构树 |
| GET | /documents/{id}/elements | 元素列表（按类型/章节） |
| GET | /parse-tasks/{id} | 解析任务状态 |

### 分段管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /chunks?kb_id=&document_id=&enabled=&chunk_metadata= | 分段列表（分页 + 元数据过滤） |
| PATCH | /chunks/{id}/metadata | 更新分段元数据 |
| POST | /chunks/batch-metadata | 批量更新分段元数据 |
| POST | /chunks/batch-status | 批量启停分段 |
| POST | /chunks/reembed | 重建分段向量 |

### 元数据 Schema

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /knowledge/{kb_id}/metadata-fields?scope= | 字段列表（按作用域过滤） |
| POST | /knowledge/{kb_id}/metadata-fields | 创建字段 |
| PUT | /knowledge/{kb_id}/metadata-fields/{id} | 更新字段 |
| PUT | /knowledge/{kb_id}/metadata-fields/reorder | 字段排序 |
| DELETE | /knowledge/{kb_id}/metadata-fields/{id}?force= | 删除字段（force 跳过影响确认） |

### 检索配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /knowledge/{kb_id}/retrieval-settings | 获取生效配置（含来源标签） |
| PUT | /knowledge/{kb_id}/retrieval-settings | 保存知识库覆盖配置 |

### 召回测试

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /knowledge/{kb_id}/retrieval-test-sets | 测试集列表 |
| POST | /knowledge/{kb_id}/retrieval-test-sets | 创建测试集 |
| GET/PUT/DELETE | /retrieval-test-sets/{id} | 测试集 CRUD |
| GET | /retrieval-test-sets/{id}/cases | 用例列表 |
| POST | /retrieval-test-sets/{id}/cases | 创建用例 |
| PUT/DELETE | /retrieval-test-cases/{id} | 用例更新/删除 |
| POST | /retrieval-test-cases/batch-status | 批量启停用例 |
| POST | /retrieval-test-sets/{id}/runs | 发起测试运行 |
| GET | /retrieval-test-runs/{id} | 运行状态（轮询） |
| GET | /retrieval-test-runs/{id}/cases | 运行用例结果 |
| POST | /retrieval-test-runs/{id}/cancel | 取消运行 |

## 9. Mock 数据

- `mock/knowledge.ts`：3 个知识库（标书库 / 合同库 / 通用库）；标书库含 3 个文档、6 个分段；3 个元数据字段（document: source / validity; chunk: clause_type）；1 个测试集含 3 个用例；检索配置含 source 标签。
- Mock 处理所有知识库/文档/分段/元数据/检索配置/召回测试路由，包含分页、元数据校验、测试运行异步模拟（2s 间隔推进状态）。

## 10. 实现步骤

1. 类型定义 + Store + Mock（Task 1–3：Schema + 元数据 API + 检索配置）。
2. 后端管线：元数据过滤 + 配置合并 + 召回测试（Task 4–8）。
3. 知识库列表（卡片网格 + 新建弹窗）。
4. 知识库详情 Tab 壳 + 文档 Tab + 分段 Tab（Task 9–10）。
5. 元数据 Tab + 设置 Tab（Task 10）。
6. 召回测试 Tab：测试集 + 用例 + 运行面板（Task 11）。
7. 全量验证 + 文档同步（Task 12）。

## 11. 验收

- [x] 新建知识库 → 卡片出现。
- [x] 进知识库 → 上传 PDF → 进度条 → 解析完成 → 列表更新。
- [x] 文档 Tab：筛选、排序、批量元数据、启停、解析状态。
- [x] 分段 Tab：结构树筛选、元数据维护、批量启停。
- [x] 元数据 Tab：双作用域字段 CRUD、内置字段保护、删除确认含影响数量。
- [x] 设置 Tab：配置来源标签展示、权重联动、模型切换提示。
- [x] 召回测试 Tab：创建测试集 → 标注期望文档 → 运行 → 查看指标 → 取消运行 → 候选详情。
- [x] 文档详情：结构树可展开，选中节点显示该节元素；表格元素渲染为表格。
- [x] 删除知识库/文档有二次确认。
- [x] `npm run build` 零错误。

## 12. 手动验证项

1. 创建自定义文档字段和分段字段。
2. 为一个文档和两个分段赋值元数据。
3. 在文档和分段列表中按元数据筛选。
4. 禁用一个文档和一个分段。
5. 编辑检索设置并确认来源标签。
6. 创建测试集和五个用例。
7. 使用覆盖 TopK 运行选中用例。
8. 检查指标、候选详情和配置快照。
9. 在 Mock 运行中取消一个运行中的测试。
10. 直接刷新每个 Tab URL 并验证状态加载。
