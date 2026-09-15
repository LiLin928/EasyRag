# Dify 知识库「父子分段」（Parent-Child Chunking）实现剖析

> 分析对象：`D:\4-MyProject\dify\dify-main`（Dify 后端源码，核心位于 `api/` 目录）
> 核心文件：`api/core/rag/index_processor/processor/parent_child_index_processor.py`

---

## 一、整体定位

父子分段是 Dify 知识库支持的三种文档分割结构之一（见 `core/rag/index_processor/constant/index_type.py`）：

| 结构类型 | 枚举值 | 说明 |
| --- | --- | --- |
| 常规分段 | `text_model` | 单层分段 |
| 问答对 | `qa_model` | 问题-答案对 |
| **父子分段** | `hierarchical_model` | 细粒度子分段检索 + 完整父分段上下文 |

索引技术另有 `economy`（经济型）/ `high_quality`（高质量，向量检索）之分，父子分段在高质量模式下使用向量索引。

**核心类**：`ParentChildIndexProcessor`，继承 `BaseIndexProcessor`，实现完整生命周期：
`extract → transform → load/index → format_preview → 检索格式化`。

---

## 二、数据模型（两层结构）

- **父分段**：`DocumentSegment`（表 `document_segments`）—— 内容载体，是最终返回给上层/LLM 的单元。
- **子分段**：`ChildChunk`（表 `child_chunks`，定义于 `models/dataset.py:1056`）—— 真正的语义检索单元。

`ChildChunk` 表关键字段：

```python
segment_id      # ← 关联父分段（document_segments.id）
document_id     # 所属文档
dataset_id
tenant_id
index_node_id   # ← 自身在向量库中的节点ID（由 uuid 生成）
index_node_hash # 内容哈希
position        # 在父分段内的序号（从 1 开始）
content         # 子分段文本
word_count
```

结构模型（`core/rag/models/document.py`）：

```python
class ParentChildChunk:            # 单组父子
    parent_content: str
    child_contents: list[str]

class ParentChildStructureChunk:   # 整篇文档的结构
    parent_child_chunks: list[ParentChildChunk]
    parent_mode: str = "paragraph"
```

父模式枚举 `ParentMode`（`core/rag/entities/processing_entities.py`）：

```python
class ParentMode(StrEnum):
    FULL_DOC = "full-doc"      # 整篇文档作为一个父分段
    PARAGRAPH = "paragraph"    # 按段落切分父分段
```

---

## 三、分割流程（`transform` 方法）

父子分段本质是**两级分词器**。

### 3.1 PARAGRAPH 模式（按段落）

1. 每篇文档先用**父分段规则**（`rules.segmentation`：`max_tokens`、`chunk_overlap`、`separator`），经 `FixedRecursiveCharacterTextSplitter` 切成父分段；
2. 为每个父分段生成 `doc_id` / `doc_hash`，并清理 Markdown 图片（提取为多模态附件）；
3. 对**每个父分段**再调用 `_split_child_nodes()`，用**子分段规则**（`rules.subchunk_segmentation`）再切一次，得到 `document_node.children`（一组 `ChildDocument`）；
4. 子分段同样分配独立的 `doc_id` / `doc_hash`。

### 3.2 FULL_DOC 模式（整篇）

- 整篇文档 `"\n".join()` 后作为**单一父分段**；
- 仅对这个父分段跑一次子分段切分。

### 3.3 分段器选择（`index_processor_base.py:_get_splitter`）

| 处理模式 | 使用的分词器 |
| --- | --- |
| `hierarchical` / `custom` | `FixedRecursiveCharacterTextSplitter`（按自定义 separator、max_tokens） |
| `automatic` | `EnhanceRecursiveCharacterTextSplitter` |

分隔符优先级：`["\n\n", "。", ". ", " ", ""]`，并基于 embedding 模型的 token 上限计算实际 chunk size。

---

## 四、向量化（`load` / `index`）—— 关键设计

**只有子分段进入向量库，父分段不入向量索引。**

```python
# load():
vector = Vector(dataset, session=session)
for document in documents:
    child_documents = document.children
    if child_documents:
        vector.create(child_documents)   # 只索引子分段
```

`index()` 方法同样只对 `all_child_documents` 执行 `vector.create()`。

这正是父子分段的核心 trade-off：**用细粒度子分段做精确语义匹配，用完整父分段提供上下文**。

---

## 五、持久化（`DatasetDocumentStore.add_documents`，`save_child=True`）

- 父分段写入 `document_segments`（初始 `enabled=False`，待后续启用/索引完成）；
- 遍历 `doc.children`，每个子分段插入一条 `ChildChunk`，记录 `segment_id=父分段id`、`index_node_id`、`position`；
- **更新场景**：先按 `(tenant_id, dataset_id, document_id, segment_id)` 删除旧子分块，再重建，保证幂等；
- 同时写入一条 `ProcessRuleMode.HIERARCHICAL` 的 `DatasetProcessRule`，标记该文档使用了父子分段规则。

---

## 六、检索（`retrieval_service.format_retrieval_documents`）

父子分段最巧妙的部分——**用子分段向量召回，映射回父分段返回**：

1. **向量检索命中的是子分块**：query 在向量库检索，返回的 `doc_id` 是子分块的 `index_node_id`，被归入 `child_index_node_ids`；
2. **反查父分段**：
   ```python
   select(ChildChunk).where(ChildChunk.index_node_id.in_(child_index_node_ids))
   # 得到子分块的 segment_id → 再查 DocumentSegment 拿到父分段
   ```
3. **评分合并**：父分段的最终得分 = 命中的多个子分块分数中的**最大值**（`max_score`），并把命中子分块详情（`content`、`position`、`score`）作为 `child_chunks` 一并返回上层；
4. 返回给上层的内容仍是**父分段完整文本**，从而同时保证**召回精度（细）**与**上下文完整（全）**。

---

## 七、清理与多模态

- `clean()`：按 `index_node_id` 找到对应 `ChildChunk.index_node_id` 删除向量，并按需删除 `child_chunks` 记录（支持预计算 child_node_ids 以规避竞态）；
- 多模态：父分段内的图片提取为 `AttachmentDocument` 并单独向量化（`vector.create_multimodal`）。

---

## 八、一句话总结

> 父子分段 = **两级切分**（父分段按段落/整篇，子分段按 subchunk 规则再切）→ **仅子分段建向量索引** → 存储时子分块通过 `segment_id` 挂在父分段下 → **检索时用子分块召回、按 `segment_id` 映射回父分段并取子分块最高分作为父分段得分**，最终向用户返回完整父分段内容。

---

## 附录：关键源码路径

| 文件 | 作用 |
| --- | --- |
| `api/core/rag/index_processor/processor/parent_child_index_processor.py` | 父子分段处理器核心 |
| `api/core/rag/index_processor/index_processor_base.py` | 基类与 `_get_splitter` 分段器 |
| `api/core/rag/index_processor/constant/index_type.py` | 索引结构/技术类型枚举 |
| `api/core/rag/models/document.py` | 父子分段结构模型 |
| `api/core/rag/docstore/dataset_docstore.py` | 文档/子分段持久化 |
| `api/core/rag/datasource/retrieval_service.py` | 检索与父子映射、评分合并 |
| `api/models/dataset.py` | `ChildChunk` 表定义 |
| `api/core/rag/entities/processing_entities.py` | `ParentMode` 枚举 |
