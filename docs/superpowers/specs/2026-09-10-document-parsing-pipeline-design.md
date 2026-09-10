# 文档解析管线设计文档

> **版本**：V1.0
> **日期**：2026-09-10
> **状态**：设计完成，待实施
> **作者**：Claude Code
> **关联文档**：
> - `CLAUDE.md` (项目开发约定)
> - `docs/backend-plans/后端开发设计方案.md` (总体架构)
> - `docs/项目总体完成报告.md` (当前状态)

---

## 1. 概述

### 1.1 背景

EasyRAG 后端开发已全部完成（94+ API，20500+ 行代码），但核心功能 `parse_document` 任务的实现仍是占位符状态。文档解析管线是 RAG 系统的核心，需要实现实际的解析逻辑：

```
文档上传 → Dispatcher → Parser → TreeBuilder → Chunker → Embedder → 存储
```

### 1.2 目标

**主要目标：**
- 实现完整的文档解析管线，支持 PDF/DOCX/XLSX/MD 格式
- 集成到现有 Celery 任务系统
- 确保端到端流程可运行

**非目标：**
- 不追求完美质量，快速验证流程
- 不集成重型解析库（MinerU），保留后续优化空间
- 不实现 OCR（现阶段），标记为后续优化

### 1.3 范围

**包含：**
- 4 种格式的解析器实现
- 文档树构建
- 语义分块
- 向量化集成
- 完整的测试覆盖

**不包含：**
- OCR 能力（Phase 4.2）
- MinerU 集成（Phase 4.2）
- 批量处理优化（Phase 4.3）

---

## 2. 总体架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────┐
│                    parse_document (Celery Task)          │
└─────────────────────┬───────────────────────────────────┘
                      │
          ┌───────────▼──────────┐
          │   DocumentDispatcher │  识别文件类型，选择解析器
          └───────────┬──────────┘
                      │
          ┌───────────▼──────────┐
          │   Parser (多格式)     │  提取文档内容和元素
          │  - PDFParser          │
          │  - DOCXParser         │
          │  - XLSXParser         │
          │  - MarkdownParser     │
          └───────────┬──────────┘
                      │
          ┌───────────▼──────────┐
          │   TreeBuilder        │  构建文档层级结构
          └───────────┬──────────┘
                      │
          ┌───────────▼──────────┐
          │   Chunker            │  语义分块，生成 chunks
          └───────────┬──────────┘
                      │
          ┌───────────▼──────────┐
          │   Embedder           │  向量化并存储到数据库
          └──────────────────────┘
```

### 2.2 架构决策

**选择流水线模式的原因：**

1. **职责分离**：每个组件单一职责，易于理解和维护
2. **可扩展性**：新增格式只需添加解析器
3. **易测试**：每个阶段独立可测
4. **Celery 友好**：完美适配异步任务模型
5. **渐进优化**：后续可替换任意组件

---

## 3. 核心数据结构

### 3.1 ParsedDocument

```python
@dataclass
class ParsedDocument:
    """解析后的文档结构"""
    doc_id: str                           # 文档 ID
    file_key: str                         # 存储路径
    elements: List[DocumentElement]       # 文档元素列表
    metadata: Dict[str, Any]              # 文档元数据
    structure: Optional[DocumentTree]     # 文档树结构
```

### 3.2 DocumentElement

```python
@dataclass
class DocumentElement:
    """文档元素"""
    element_id: str                       # 元素 ID
    element_type: str                     # 类型：paragraph, heading, table, image, list
    content: str                          # 文本内容
    position: ElementPosition             # 位置信息
    metadata: Dict[str, Any]              # 元数据（字体、样式等）
```

### 3.3 DocumentTree

```python
@dataclass
class DocumentTree:
    """文档树结构"""
    root: TreeNode                        # 根节点
    nodes: List[TreeNode]                 # 所有节点扁平列表

@dataclass
class TreeNode:
    """树节点"""
    node_id: str                          # 节点 ID
    level: int                            # 层级深度
    title: str                            # 节点标题
    element_ids: List[str]                # 包含的元素 ID
    children: List[str]                   # 子节点 ID 列表
```

---

## 4. 组件详细设计

### 4.1 DocumentDispatcher

**职责：**
- 识别文件类型
- 选择合适的解析器
- 处理解析错误
- 更新文档状态

**文件位置：** `app/core/parser/dispatcher.py`

**核心方法：**

```python
async def dispatch(self, doc_id: str, file_key: str) -> ParsedDocument:
    """
    调度文档解析

    Args:
        doc_id: 文档 ID
        file_key: 存储路径

    Returns:
        ParsedDocument: 解析结果

    Raises:
        UnsupportedFormatError: 不支持的格式
        ParseFailedError: 解析失败
    """
```

**解析器映射：**

| 扩展名 | 解析器 | 说明 |
|--------|--------|------|
| pdf | PDFParser | PyMuPDF |
| docx, doc | DOCXParser | python-docx |
| xlsx, xls | XLSXParser | openpyxl |
| md, markdown | MarkdownParser | markdown-it |
| txt | TextParser | 简单文本 |

---

### 4.2 Parser 家族

**基类：** `app/core/parser/base.py`

```python
class BaseParser(ABC):
    """解析器基类"""

    @abstractmethod
    async def parse(self, file_data: bytes, doc_id: str) -> ParsedDocument:
        """解析文档"""
        pass
```

#### 4.2.1 PDFParser

**文件：** `app/core/parser/pdf_parser.py`
**依赖：** PyMuPDF (fitz)

**能力：**
- ✅ 文本块提取
- ✅ 表格识别（基础）
- ✅ 图片位置记录
- ✅ 元数据提取
- ⏳ 表格结构化（后续）
- ⏳ OCR（后续）

**实现要点：**

```python
async def parse(self, file_data: bytes, doc_id: str) -> ParsedDocument:
    # 1. 打开 PDF
    pdf_document = fitz.open(stream=file_data, filetype='pdf')

    # 2. 逐页提取
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        blocks = page.get_text('dict')['blocks']

        for block in blocks:
            if 'lines' in block:  # 文本块
                element = self._create_text_element(block, page_num)

    # 3. 返回结果
    return ParsedDocument(...)
```

#### 4.2.2 DOCXParser

**文件：** `app/core/parser/docx_parser.py`
**依赖：** python-docx

**能力：**
- ✅ 段落提取
- ✅ 标题识别
- ✅ 列表处理
- ⏳ 表格处理（后续）
- ⏳ 图片提取（后续）

#### 4.2.3 XLSXParser

**文件：** `app/core/parser/xlsx_parser.py`
**依赖：** openpyxl

**能力：**
- ✅ 工作表遍历
- ✅ 单元格内容提取
- ⏳ 公式处理（后续）

#### 4.2.4 MarkdownParser

**文件：** `app/core/parser/markdown_parser.py`
**依赖：** markdown-it-py

**能力：**
- ✅ 标题层级识别
- ✅ 代码块提取
- ✅ 列表处理
- ✅ 链接和图片

---

### 4.3 TreeBuilder

**文件：** `app/core/parser/tree_builder.py`

**职责：**
- 分析文档结构
- 识别标题层级
- 构建导航树
- 保存到数据库

**标题识别规则：**

```python
HEADING_PATTERNS = [
    r'^#+\s+',                        # Markdown 标题
    r'^第[一二三四五六七八九十]+[章节篇]',  # 中文章节
    r'^\d+\.\d*\s+',                  # 数字编号
]
```

**核心算法：**

```python
async def build(self, elements: List[DocumentElement], doc_id: str) -> DocumentTree:
    # 1. 识别标题节点
    nodes = [self._create_node(elem) for elem in elements if self._is_heading(elem)]

    # 2. 构建层级关系
    root = TreeNode(node_id='root', level=0, ...)
    stack = [root]

    for node in nodes:
        # 找到合适的父节点
        while stack[-1].level >= node.level:
            stack.pop()

        stack[-1].children.append(node.node_id)
        stack.append(node)

    # 3. 保存到数据库
    await self._save_tree(root, nodes, doc_id)

    return DocumentTree(root=root, nodes=nodes)
```

---

### 4.4 Chunker

**文件：** `app/core/parser/chunker.py`

**职责：**
- 语义分块
- 控制块大小
- 保留上下文
- 保存到数据库

**分块策略：**

```python
class Chunker:
    def __init__(
        self,
        chunk_size: int = 512,      # 目标块大小
        chunk_overlap: int = 50,    # 重叠字符数
        min_chunk_size: int = 100   # 最小块大小
    ):
        ...
```

**分块算法：**

```python
async def chunk(self, elements: List[DocumentElement], doc_id: str, kb_id: str) -> List[Chunk]:
    chunks = []
    current_chunk = []
    current_size = 0

    for elem in elements:
        # 检查是否需要新块
        if current_size + len(elem.content) > self.chunk_size:
            # 保存当前块
            if current_size >= self.min_chunk_size:
                chunks.append(self._create_chunk(current_chunk, doc_id, kb_id))

            # 重叠处理
            current_chunk = self._get_overlap(current_chunk)
            current_size = sum(len(e.content) for e in current_chunk)

        current_chunk.append(elem)
        current_size += len(elem.content)

    # 保存最后一块
    if current_chunk:
        chunks.append(self._create_chunk(current_chunk, doc_id, kb_id))

    await self._save_chunks(chunks)
    return chunks
```

---

### 4.5 Embedder

**文件：** `app/core/parser/embedder.py`

**职责：**
- 批量向量化 chunks
- 调用已配置的 Embedding 模型
- 存储向量到数据库
- 错误重试

**实现要点：**

```python
async def embed(self, chunks: List[Chunk], kb_id: str) -> int:
    # 1. 获取知识库的 Embedding 模型
    kb = await session.get(KnowledgeBase, kb_id)
    model_config = await session.get(ModelConfig, kb.embedding_model_id)

    # 2. 构建 Embedder
    embeddings = await build_embeddings(model_config)

    # 3. 批量处理
    for i in range(0, len(chunks), self.batch_size):
        batch = chunks[i:i + self.batch_size]
        texts = [chunk.content for chunk in batch]

        # 向量化
        vectors = await embeddings.aembed_documents(texts)

        # 更新数据库
        await self._update_embeddings(batch, vectors)

        # 发送进度
        await self._publish_progress(len(chunks), i + len(batch), kb_id)
```

---

## 5. 错误处理

### 5.1 错误分类

```python
class ParseError(Exception):
    """解析错误基类"""
    pass

class UnsupportedFormatError(ParseError):
    """不支持的格式"""
    pass

class ParseFailedError(ParseError):
    """解析失败"""
    pass

class EmbeddingFailedError(ParseError):
    """向量化失败"""
    pass
```

### 5.2 重试策略

| 错误类型 | 重试 | 最大次数 | 延迟策略 | 失败后动作 |
|---------|------|---------|---------|-----------|
| ParseFailedError | 否 | - | - | 标记失败，不重试 |
| EmbeddingFailedError | 是 | 3 | 指数退避 (60s, 120s, 180s) | 标记部分完成 |
| UnknownError | 是 | 3 | 指数退避 | 标记失败 |

### 5.3 状态管理

**文档状态流转：**

```
pending → parsing → parsed → chunking → chunked → embedding → success
    ↓         ↓          ↓         ↓          ↓
  failed   failed    failed    failed      partial
```

**状态更新：**

```python
async def update_document_status(doc_id: str, status: str, error_msg: str = None):
    """更新文档状态"""
    async with async_session() as session:
        doc = await session.get(Document, doc_id)
        doc.status = status
        if error_msg:
            doc.error_message = error_msg
        await session.commit()
```

---

## 6. 测试策略

### 6.1 测试数据集

**目录结构：**

```
tests/fixtures/documents/
├── pdf/
│   ├── simple.pdf          # 简单文本
│   ├── with_tables.pdf     # 包含表格
│   ├── with_images.pdf     # 包含图片
│   ├── multi_page.pdf      # 多页文档
│   └── chinese.pdf         # 中文文档
├── docx/
│   ├── simple.docx
│   ├── with_styles.docx    # 包含样式
│   └── with_lists.docx     # 包含列表
├── xlsx/
│   ├── simple.xlsx
│   └── multi_sheet.xlsx    # 多工作表
└── md/
    ├── simple.md
    └── with_code.md        # 包含代码块
```

### 6.2 单元测试

**测试覆盖率要求：** ≥ 80%

**测试用例示例：**

```python
# tests/test_parser/test_pdf_parser.py

@pytest.mark.asyncio
async def test_simple_pdf():
    """测试简单 PDF"""
    parser = PDFParser()
    with open('tests/fixtures/documents/pdf/simple.pdf', 'rb') as f:
        result = await parser.parse(f.read(), 'test-doc')

    assert len(result.elements) > 0
    assert all(elem.element_type in ['paragraph', 'heading']
               for elem in result.elements)

@pytest.mark.asyncio
async def test_pdf_with_tables():
    """测试包含表格的 PDF"""
    parser = PDFParser()
    with open('tests/fixtures/documents/pdf/with_tables.pdf', 'rb') as f:
        result = await parser.parse(f.read(), 'test-doc')

    table_elements = [e for e in result.elements
                      if e.element_type == 'table']
    assert len(table_elements) > 0
```

### 6.3 集成测试

```python
# tests/test_parser/test_integration.py

@pytest.mark.asyncio
async def test_full_pipeline():
    """测试完整解析流程"""
    # 1. 上传测试文件
    doc_id = await upload_test_file('sample.pdf')

    # 2. 执行解析
    dispatcher = DocumentDispatcher()
    parsed_doc = await dispatcher.dispatch(doc_id, 'test.pdf')

    # 3. 验证结果
    assert len(parsed_doc.elements) > 0
    assert parsed_doc.structure is not None

    # 4. 验证分块
    chunks = await get_chunks(doc_id)
    assert len(chunks) > 0
    assert all(chunk.embedding is not None for chunk in chunks)
```

### 6.4 性能测试

```python
@pytest.mark.asyncio
async def test_parse_performance():
    """测试解析性能 (< 30秒)"""
    start = time.time()

    dispatcher = DocumentDispatcher()
    await dispatcher.dispatch('test-doc', 'sample.pdf')

    elapsed = time.time() - start
    assert elapsed < 30, f"Parse took {elapsed}s, expected < 30s"
```

---

## 7. 依赖管理

### 7.1 新增依赖

```toml
[project.dependencies]
# PDF 解析
PyMuPDF = ">=1.23.0"

# DOCX 解析
python-docx = ">=0.8.11"

# XLSX 解析
openpyxl = ">=3.1.2"

# Markdown 解析
markdown-it-py = ">=3.0.0"
```

### 7.2 安装命令

```bash
cd backend
uv add PyMuPDF python-docx openpyxl markdown-it-py
uv lock
```

---

## 8. 实施计划

### 8.1 阶段划分

| 阶段 | 任务 | 预计时间 | 验收标准 |
|------|------|---------|---------|
| 阶段 1 | 基础设施搭建 | 2-3 天 | 核心数据结构完成，测试框架可用 |
| 阶段 2 | 解析器实现 | 5-7 天 | 4 个解析器可用，测试覆盖率 ≥ 80% |
| 阶段 3 | 结构处理 | 3-4 天 | TreeBuilder 和 Chunker 可用 |
| 阶段 4 | 向量化集成 | 2-3 天 | Embedder 可用，端到端可运行 |
| 阶段 5 | 集成优化 | 3-4 天 | 所有测试通过，文档完整 |

### 8.2 总时间

**预计总时间：** 15-21 天

---

## 9. 风险控制

### 9.1 风险矩阵

| 风险项 | 概率 | 影响 | 缓解措施 |
|--------|------|------|---------|
| 测试文档不足 | 中 | 中 | 使用公开文档样本库 |
| 解析质量不达标 | 高 | 高 | 分阶段验证，快速迭代 |
| 性能不满足要求 | 中 | 高 | 性能测试，识别瓶颈 |
| 依赖库版本冲突 | 低 | 中 | 使用 uv 管理依赖 |
| Embedding API 不稳定 | 中 | 中 | 重试机制，降级策略 |

### 9.2 回滚计划

如果实施遇到重大问题：

1. **保留占位符代码**：原始 `parse_document` 任务不变
2. **分支隔离**：在独立分支开发，不合并到主分支
3. **标记 TODO**：未完成功能标记清晰，不影响其他模块

---

## 10. 成功指标

### 10.1 功能指标

- ✅ 支持 PDF/DOCX/XLSX/MD 4 种格式
- ✅ 每种格式至少 5 个单元测试
- ✅ 测试覆盖率 ≥ 80%
- ✅ 端到端流程可运行

### 10.2 性能指标

- ✅ 单文档解析时间 < 30 秒（中小文档）
- ✅ 批量向量化成功率 > 95%
- ✅ 内存占用 < 500MB（单文档）

### 10.3 质量指标

- ✅ 所有测试通过
- ✅ 无已知 Bug
- ✅ 代码符合规范（有 docstring）
- ✅ 文档完整

---

## 11. 后续优化

### 11.1 短期优化（Phase 4.1）

- 增加更多格式支持（TXT, HTML, RTF）
- 优化表格提取质量
- 添加文档去重功能

### 11.2 中期优化（Phase 4.2）

- 集成 MinerU 提升质量
- 添加 OCR 能力
- 支持批量文档处理

### 11.3 长期优化（Phase 4.3）

- 智能分块算法
- 多语言支持
- 自定义解析规则

---

## 12. 附录

### 12.1 相关文档

- `docs/backend-plans/后端开发设计方案.md` - 总体架构设计
- `docs/superpowers/plans/2026-08-08-phase1-knowledge-parsing.md` - 知识库解析计划
- `docs/本地开发测试指南.md` - 开发环境配置

### 12.2 参考资源

- [PyMuPDF 文档](https://pymupdf.readthedocs.io/)
- [python-docx 文档](https://python-docx.readthedocs.io/)
- [openpyxl 文档](https://openpyxl.readthedocs.io/)
- [markdown-it-py 文档](https://markdown-it-py.readthedocs.io/)

---

**文档状态：** ✅ 设计完成，待用户审核
**下一步：** 用户审核通过后，创建详细实施计划