# 知识库元数据、检索配置与召回测试设计

- 日期：2026-08-17
- 状态：已确认
- 范围：知识库管理前端、知识库/文档/分块数据模型、检索管线、召回测试 API 与异步执行

## 1. 背景

当前 EasyRAG 已具备知识库、文档、解析、结构树、元素浏览和混合检索管线，但检索参数主要来自全局场景预设，模型选择集中在系统设置，知识库自身不能独立调整 Embedding、Rerank 和检索策略。文档与分块也缺少可管理的业务属性，无法按来源、效力级别、条款类型、生效状态等条件过滤。

本设计将知识库详情升级为完整管理闭环：

1. 文档与分段的资产化管理
2. 双作用域元数据模型
3. 知识库级 Embedding、Rerank 与检索策略配置
4. 可保存的召回测试集与批量回归指标

## 2. 目标与非目标

### 目标

- 知识库详情提供 `文档 / 分段 / 元数据 / 召回测试 / 设置` 五个标签页。
- 元数据字段支持 `document` 与 `chunk` 两种作用域，可定义类型、必填、筛选、检索过滤和展示属性。
- 文档和分段均可单独维护元数据、启停状态和召回统计。
- 每个知识库可绑定自己的 Embedding 与 Rerank 模型，并覆盖场景中的检索参数。
- 支持可保存测试集、批量异步执行、指标汇总、失败用例明细和配置快照。
- 召回测试 V1 按文档级期望命中计算指标。

### 非目标

- 不做自动生成测试集或答案。
- 不集成 RAGAS 等生成质量评估。
- 不做多版本索引并行在线 A/B 检索。
- 不支持直接自由编辑分段正文；原文修正进入后续人工修订流。
- V1 不开放分段级期望命中标注，仅保留数据结构。
- V1 不改变 `vector(1024)` 固定向量维度。

## 3. 信息架构与页面设计

### 3.1 知识库详情

路由保持：

```text
/knowledge/:kbId
```

页面结构：

```text
知识库页头
  名称、描述、文档数、分页数、分段数、最近测试时间
  上传文档、运行测试

Tabs
  文档 | 分段 | 元数据 | 召回测试 | 设置
```

页面遵循现有 Vue 3 + Element Plus 管理后台风格：白底面板、8px 圆角、紧凑表格、蓝色主按钮、明确加载与错误状态。

### 3.2 文档页

文档页面向资产运营，核心是筛选、状态、分段健康度与批量操作。

工具栏：

- 文档名搜索
- 状态筛选：全部 / 待解析 / 解析中 / 已完成 / 失败
- 元数据筛选：来源、效力级别、年份等由 schema 生成
- 排序：上传时间、文档名、分段数、召回次数
- 列设置

表格列：

- 选择框
- 文档名、大小、页数、上传时间
- 解析状态与进度
- 分段数
- 召回次数
- 元数据标签
- 解析模式：快速 / 精准
- 启用开关
- 操作：详情、元数据、进度、重试

批量操作：

- 编辑元数据
- 启用 / 禁用
- 重建索引
- 删除（二次确认）

设计约束：

- 禁用文档不参与默认检索。
- 必填元数据缺失用字段级红标签提示，不用整行红色干扰扫描。
- 解析失败可展开错误原因并提供重试。

### 3.3 分段页

分段页面向检索资产管理，保留结构树导航。

布局：

```text
左侧：文档结构树
右侧：分段筛选、分段表格、原文与元数据面板
```

筛选：

- 分段内容搜索
- 文档筛选
- 向量状态：全部 / 已向量化 / 未向量化
- 元数据筛选：条款类型、生效状态、适用阶段等
- 标签或类型筛选

表格列：

- 选择框
- 分段摘要、分段序号、类型
- 所属文档、章节、页码
- 分段元数据标签
- 字符数
- Embedding 模型
- 召回次数
- 启用状态
- 操作：元数据、启停、向量化

底部详情面板：

- 原文预览
- 定位：文档、章节、页码、序号
- 质量：字符数、向量模型、召回次数、最近命中时间
- 分段元数据标签与编辑入口

分段支持：

- 启用 / 禁用
- 单个与批量元数据维护
- 缺失向量批量重建
- 查看命中历史入口

分段不允许直接自由编辑正文，避免破坏原文引用和追溯链路。

### 3.4 元数据页

元数据页采用双作用域 Schema。

字段属性：

- 字段名：展示名
- 标识：英文 key
- 作用域：`document` / `chunk`
- 类型：文本、数字、日期、单选、布尔
- 必填
- 列表筛选
- 检索过滤
- 默认展示
- 启用
- 排序

内置文档字段：

- `document_name`：映射 `documents.name`
- `file_size`：映射 `documents.size`
- `uploader`：映射上传用户
- `upload_date`：映射创建时间
- `last_update_date`：映射更新时间
- `source`：存储在文档 metadata 中，可作为内置可编辑字段

内置字段可启用、停用和配置展示，不可删除、不可改 key 和类型。

分段字段示例：

- `clause_type`：条款类型
- `effective_status`：生效状态
- `effective_date`：生效日期
- `applicable_stage`：适用阶段
- `reviewed`：人工校验

标记为 `retrieval_filterable` 的字段可进入检索请求。检索时必须按当前知识库 schema 校验字段与值类型，防止任意 JSONB 注入。

### 3.5 召回测试页

布局：

```text
左侧：测试集列表
右侧：测试集详情、用例表、运行结果、命中明细
```

测试集卡片：

- 名称
- 用例数
- 最近运行时间
- 最近指标摘要
- 状态：草稿 / 最新 / 归档

用例表：

- 选择框
- 查询文本
- 期望文档
- 标签
- 首个期望文档命中排名
- 命中状态：命中 / 部分命中 / 未命中 / 失败 / 跳过
- 耗时
- 操作：编辑、运行此用例、查看明细

批量操作：

- 新增用例
- 批量启停
- 批量运行
- 标签筛选
- 查看历史运行

指标卡：

- `Hit@K`
- `Recall@K`
- `MRR`
- `P50 / P95 latency`
- Rerank 触发率

命中明细：

- 每个返回分段的文档、章节、页码、字符数
- 向量分、关键词分、RRF 分、Rerank 分
- 向量排名、关键词排名、最终排名
- 命中的期望文档高亮

生效配置面板展示每个值的来源：

- `测试覆盖`
- `知识库覆盖`
- `场景默认`
- `系统默认`

### 3.6 设置页

设置页左侧分组：

- 索引模型
- 检索策略
- Rerank
- 结构导航
- 风险操作

配置项：

- Embedding 模型
- 检索模式：向量 / 混合 / 关键词
- 最终 TopK
- 向量候选 TopK
- 关键词候选 TopK
- 分数阈值
- 向量权重与关键词权重
- RRF K
- Rerank 开关、模型、候选数、触发阈值
- 结构导航开关、锚点数、置信度
- 分块大小与重叠

保存前校验：

- 向量权重 + 关键词权重 = 1
- TopK、阈值、分块大小在合法范围内
- Embedding 模型维度与当前索引兼容
- Rerank 模型可用

高风险操作：

- 更换 Embedding：提示需重建向量，展示影响分段数。
- 修改分块大小：提示会生成分段版本；历史测试结果按当时配置快照展示。
- 重建索引：二次确认并展示任务进度。

## 4. 数据模型

### 4.1 知识库

`knowledge_bases` 新增字段：

```text
embedding_model_id UUID NULL FK model_configs.id
rerank_model_id    UUID NULL FK model_configs.id
retrieval_config   JSONB NOT NULL DEFAULT '{}'
```

现有字段继续使用：

- `chunk_size`
- `chunk_overlap`
- `retrieval_top_k` 作为最终 TopK

`retrieval_config` 结构：

```json
{
  "method": "hybrid",
  "vector_top_k": 20,
  "keyword_top_k": 20,
  "similarity_threshold": 0.3,
  "vector_weight": 0.6,
  "keyword_weight": 0.4,
  "rrf_k": 60,
  "rerank_enabled": true,
  "rerank_top_n": 10,
  "rerank_trigger_threshold": 0.02,
  "navigation_enabled": true,
  "nav_anchor_count": 3,
  "nav_confidence_threshold": 0.15
}
```

字段可部分存在；未设置的项回退到场景配置。

### 4.2 元数据字段

新增表：`kb_metadata_fields`

```text
id                    UUID PK
kb_id                 UUID NOT NULL FK knowledge_bases.id ON DELETE CASCADE
key                   VARCHAR(64) NOT NULL
name                  VARCHAR(100) NOT NULL
scope                 VARCHAR(16) NOT NULL -- document / chunk
data_type             VARCHAR(16) NOT NULL -- string / number / date / select / boolean
options               JSONB NOT NULL DEFAULT '[]'
default_value         JSONB NULL
required              BOOLEAN NOT NULL DEFAULT false
filterable            BOOLEAN NOT NULL DEFAULT false
retrieval_filterable  BOOLEAN NOT NULL DEFAULT false
visible               BOOLEAN NOT NULL DEFAULT true
built_in              BOOLEAN NOT NULL DEFAULT false
mapped_field          VARCHAR(64) NULL
sort_order            INTEGER NOT NULL DEFAULT 0
created_at            TIMESTAMP
updated_at            TIMESTAMP

UNIQUE(kb_id, scope, key)
```

约束：

- `scope` 仅允许 `document` / `chunk`
- `data_type=select` 时 `options` 必须非空且不重复
- `built_in=true` 的字段不可删除
- `mapped_field` 非空时值来自物理字段，不复制到 JSONB

### 4.3 文档与分块

`documents` 新增：

```text
metadata     JSONB NOT NULL DEFAULT '{}'
enabled      BOOLEAN NOT NULL DEFAULT true
recall_count INTEGER NOT NULL DEFAULT 0
```

`chunks` 新增：

```text
metadata     JSONB NOT NULL DEFAULT '{}'
enabled      BOOLEAN NOT NULL DEFAULT true
recall_count INTEGER NOT NULL DEFAULT 0
char_count   INTEGER NOT NULL DEFAULT 0
```

说明：

- 文档与分段元数据 key 必须存在于对应 scope 的启用字段。
- 生产对话检索命中时累加召回次数。
- 召回测试运行不累加召回次数，避免测试流量污染运营统计。
- 默认检索过滤 `documents.enabled=true` 与 `chunks.enabled=true`。

### 4.4 召回测试

新增表：`retrieval_test_sets`

```text
id          UUID PK
kb_id       UUID NOT NULL FK knowledge_bases.id ON DELETE CASCADE
name        VARCHAR(100) NOT NULL
description TEXT NULL
archived    BOOLEAN NOT NULL DEFAULT false
created_at  TIMESTAMP
updated_at  TIMESTAMP
```

新增表：`retrieval_test_cases`

```text
id                  UUID PK
test_set_id         UUID NOT NULL FK retrieval_test_sets.id ON DELETE CASCADE
query               TEXT NOT NULL
expected_doc_ids    JSONB NOT NULL DEFAULT '[]'
expected_chunk_ids  JSONB NOT NULL DEFAULT '[]'
tags                JSONB NOT NULL DEFAULT '[]'
enabled             BOOLEAN NOT NULL DEFAULT true
sort_order          INTEGER NOT NULL DEFAULT 0
created_at          TIMESTAMP
updated_at          TIMESTAMP
```

`expected_chunk_ids` 仅预留字段，V1 不开放编辑且不参与指标。

新增表：`retrieval_test_runs`

```text
id                 UUID PK
test_set_id        UUID NOT NULL FK retrieval_test_sets.id
kb_id              UUID NOT NULL FK knowledge_bases.id
status             VARCHAR(16) NOT NULL -- pending / running / completed / failed / canceled
config_snapshot    JSONB NOT NULL DEFAULT '{}'
override_config    JSONB NOT NULL DEFAULT '{}'
total_cases        INTEGER NOT NULL DEFAULT 0
completed_cases    INTEGER NOT NULL DEFAULT 0
metrics            JSONB NOT NULL DEFAULT '{}'
error              TEXT NULL
started_at         TIMESTAMP NULL
finished_at        TIMESTAMP NULL
created_at         TIMESTAMP
```

新增表：`retrieval_test_case_results`

```text
id                UUID PK
run_id            UUID NOT NULL FK retrieval_test_runs.id ON DELETE CASCADE
case_id           UUID NULL FK retrieval_test_cases.id ON DELETE SET NULL
query             TEXT NOT NULL
status            VARCHAR(16) NOT NULL -- pending / running / hit / partial_hit / miss / failed / skipped
expected_doc_ids  JSONB NOT NULL DEFAULT '[]'
hit_doc_ids       JSONB NOT NULL DEFAULT '[]'
results           JSONB NOT NULL DEFAULT '[]'
metrics           JSONB NOT NULL DEFAULT '{}'
latency_ms        INTEGER NULL
error             TEXT NULL
created_at        TIMESTAMP
```

`results` 保存每个候选分段的完整信息：

```json
{
  "rank": 1,
  "chunk_id": "...",
  "document_id": "...",
  "document_name": "...",
  "section_path": "...",
  "page_number": 12,
  "char_count": 549,
  "vector_score": 0.91,
  "keyword_score": 0.43,
  "vector_rank": 1,
  "keyword_rank": 3,
  "rrf_score": 0.032,
  "rerank_score": 0.94,
  "metadata": {}
}
```

## 5. 配置合并与检索行为

### 5.1 配置优先级

```text
测试或请求临时覆盖
  > 知识库配置
  > 知识库绑定场景
  > general 场景
  > 代码默认值
```

生效配置必须返回：

```json
{
  "value": "...",
  "source": "override | knowledge_base | scene | system_default"
}
```

### 5.2 模型选择

- Embedding 优先使用 `knowledge_bases.embedding_model_id`。
- 未绑定时回退系统 `(embed, retrieval)` 默认模型。
- Rerank 优先使用 `knowledge_bases.rerank_model_id`。
- 未绑定时回退系统 `(rerank, rerank)` 默认模型。
- 查询向量必须与候选分块向量使用同一模型。

V1 固定 1024 维，只允许选择兼容 1024 维的 Embedding 模型。切换模型后必须重建索引；重建完成前旧向量不可用于新模型检索。

多知识库检索时：

1. 按各知识库 embedding 配置分组。
2. 每组使用对应模型查询。
3. 过滤 `embedding_model` 匹配的分段。
4. 组内执行检索与 Rerank。
5. 跨组按 rank 或 RRF 融合，不直接比较不同模型原始分数。

### 5.3 元数据过滤

检索请求可带：

```json
{
  "document_metadata": {
    "source": "国务院",
    "legal_level": ["法律", "行政法规"]
  },
  "chunk_metadata": {
    "effective_status": "现行有效"
  }
}
```

规则：

- 仅接受当前知识库 schema 中 `retrieval_filterable=true` 的字段。
- 单选字段允许多值 OR。
- 数字支持 `eq / in / gt / gte / lt / lte`。
- 日期支持范围。
- 布尔支持 true / false。
- 生成参数化 SQL 条件，禁止拼接用户输入。

## 6. 指标算法

对 `expected_doc_ids` 非空且执行成功的用例计算质量指标。

设：

- `E` 为期望文档集合
- `R` 为 Top K 返回结果映射出的文档集合，保持排名顺序
- `H = E ∩ R`

### Hit@K

```text
hit = 1 if |H| > 0 else 0
Hit@K = sum(hit) / evaluated_case_count
```

### Recall@K

```text
Recall@K = |H| / |E|
平均值 = sum(Recall@K) / evaluated_case_count
```

### MRR

第一个期望文档在返回列表中的排名为 `rank`：

```text
RR = 1 / rank，未命中为 0
MRR = sum(RR) / evaluated_case_count
```

### 其他指标

- `P50 / P95 latency`：按成功用例耗时计算，使用 nearest-rank 分位数。
- `Rerank trigger rate`：触发 Rerank 的成功用例 / 成功用例。
- `Navigation scoped rate`：结构导航成功缩域的成功用例 / 成功用例。
- `Failure rate`：失败用例 / 应执行用例。

未标注期望文档的用例只计入延迟与运行信息，不计入质量指标。

支持 `K=3 / 5 / 10` 对比；默认使用知识库最终 TopK。

## 7. API 设计

### 7.1 元数据 Schema

```text
GET    /knowledge/{kb_id}/metadata-fields
POST   /knowledge/{kb_id}/metadata-fields
PUT    /knowledge/metadata-fields/{field_id}
DELETE /knowledge/metadata-fields/{field_id}
```

删除自定义字段前返回影响数量；字段有值时必须显式确认。

### 7.2 文档与分段元数据

```text
GET   /documents
PATCH /documents/{doc_id}/metadata
POST  /documents/batch-metadata
POST  /documents/batch-status

GET   /chunks
PATCH /chunks/{chunk_id}/metadata
POST  /chunks/batch-metadata
POST  /chunks/batch-status
POST  /chunks/reembed
```

`GET /documents` 与 `GET /chunks` 支持 keyword、status、metadata filter、sort、page、pageSize。

### 7.3 知识库检索配置

```text
GET /knowledge/{kb_id}/retrieval-settings
PUT /knowledge/{kb_id}/retrieval-settings
```

返回实际值与来源，保存时执行第 3.6 节校验。

### 7.4 召回测试

```text
GET    /knowledge/{kb_id}/retrieval-test-sets
POST   /knowledge/{kb_id}/retrieval-test-sets
GET    /retrieval-test-sets/{set_id}
PUT    /retrieval-test-sets/{set_id}
DELETE /retrieval-test-sets/{set_id}

GET    /retrieval-test-sets/{set_id}/cases
POST   /retrieval-test-sets/{set_id}/cases
PUT    /retrieval-test-cases/{case_id}
DELETE /retrieval-test-cases/{case_id}
POST   /retrieval-test-cases/batch-status

POST   /retrieval-test-sets/{set_id}/runs
GET    /retrieval-test-runs/{run_id}
GET    /retrieval-test-runs/{run_id}/cases
POST   /retrieval-test-runs/{run_id}/cancel
```

运行请求：

```json
{
  "case_ids": [],
  "ks": [3, 5, 10],
  "override_config": {
    "method": "hybrid",
    "vector_weight": 0.6,
    "keyword_weight": 0.4,
    "rerank_enabled": true
  },
  "document_metadata": {},
  "chunk_metadata": {}
}
```

V1 使用异步任务与前端轮询。同一测试集同时只允许一个 `pending / running` run。

## 8. 执行流程

1. 校验测试集归属当前用户与知识库。
2. 获取启用用例；为空则拒绝运行。
3. 合并配置并生成 `config_snapshot`。
4. 创建 `pending` run 与 `pending` case result。
5. 异步任务逐条执行：
   - 查询向量化
   - 可选结构导航缩域
   - 按检索模式执行向量 / 关键词 / 混合检索
   - RRF 融合
   - 可选 Rerank
   - 计算单用例指标与耗时
   - 更新 run 进度
6. 全部完成后汇总指标，标记 `completed`。
7. 任一阶段出现模型不可用等终止性错误：
   - 已完成用例保留结果
   - 未执行用例标记 `skipped`
   - run 标记 `failed` 并记录 error

单条用例的检索异常只将该用例标记为 `failed`，不终止整个 run。

## 9. 错误处理

- 未配置 Embedding：运行失败，提示去系统设置或知识库设置配置模型。
- Embedding 维度不兼容：保存知识库设置时拒绝。
- Rerank 模型调用失败：对应用例 failed；可选择回退不重排，但必须在结果中标注。
- 测试集为空：返回参数错误。
- 重复运行：返回当前 running run 信息。
- 元数据值类型不匹配：字段级错误，不落库。
- 删除有值字段：返回影响数量并要求确认。
- 重建索引中断：任务可重试，已重建分段的 `embedding_model` 更新，未重建分段保持旧模型并可筛选。

## 10. 权限与安全

- 所有知识库、测试集、字段、文档、分段资源必须校验当前用户归属。
- API key 只在服务端读取与解密，不返回前端。
- 元数据过滤使用参数化 SQL。
- 模型配置 ID 必须属于允许的 group 和 use。
- 测试运行不暴露原始 API key 或完整 provider 配置。

## 11. 测试策略

### 后端单元测试

- 配置合并：覆盖 > 知识库 > 场景 > 默认。
- 元数据 schema 校验：scope、类型、select options、key 唯一性。
- 指标计算：Hit@K、Recall@K、MRR、部分命中、未命中、未标注用例。
- 检索模式：vector、keyword、hybrid。
- Rerank 开关与触发条件。
- 元数据过滤参数化与非法字段拒绝。

### 后端集成测试

- 创建知识库字段并读取生效 schema。
- 上传文档后补充文档与分段元数据。
- 禁用文档或分段后默认检索不返回。
- 创建测试集、用例、发起运行、轮询完成、读取结果。
- 模型失败时 run 状态与部分结果保留。
- 越权访问返回禁止或不存在。

### 前端验证

- `npm run build` 零错误。
- 文档页：筛选、排序、批量元数据、启停、解析状态。
- 分段页：结构树筛选、元数据维护、批量向量化。
- 元数据页：双作用域字段 CRUD、内置字段保护。
- 召回测试页：创建测试集、标注期望文档、批量运行、查看指标与失败明细。
- 设置页：配置来源展示、权重联动、模型切换提示。

## 12. 实施顺序

1. 数据迁移与双作用域元数据 Schema。
2. 文档 / 分段元数据 API 与列表增强。
3. 知识库级检索配置、模型绑定与配置合并。
4. 检索管线支持模式选择、元数据过滤与阶段分数。
5. 召回测试集、异步 run 与指标计算。
6. 前端五个标签页与召回测试工作台。
7. 集成测试、构建验收与设计文档同步。

## 13. 验收标准

- 每个知识库可独立设置 Embedding、Rerank、检索模式、权重、TopK、Rerank 和结构导航参数。
- 文档和分段元数据均可定义、筛选、批量编辑。
- 标记检索过滤的元数据能实际影响检索结果。
- 测试集可保存并重复运行。
- 批量结果包含 Hit@K、Recall@K、MRR、P50/P95 延迟与 Rerank 触发率。
- 失败用例可定位到具体分段、分数和排名。
- 每次 run 可查看当时完整配置快照。
- 禁用文档或分段后不再参与默认检索。
- 后端相关测试与前端 `npm run build` 通过。
