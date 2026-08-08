# 11 · 系统设置 Settings

> 原型页面：page-settings。模型配置（LLM/Embedding/Rerank 三组，多供应商）+ 场景预设管理。

## 1. 目标

左侧分组导航（LLM / Embedding / Rerank / 场景），右侧对应配置。模型支持多供应商多实例、按用途、设默认；切换 Embedding 提示重建索引。场景预设 CRUD。

## 2. 组件清单（views/settings/）

| 组件 | 路径 | 职责 |
|------|------|------|
| SettingsView | SettingsView.vue | 容器：左侧分组导航 + 右侧 router-view/动态区 |
| ModelGroupPanel | components/ModelGroupPanel.vue | 单组模型面板：分组说明 + 模型表格 + 「添加模型」+ 默认标记 |
| ModelRow | components/ModelRow.vue | 模型行：名称/供应商/用途/温度/上下文/默认/编辑/删除 |
| ModelConfigDialog | components/ModelConfigDialog.vue | el-dialog：名称/供应商(下拉)/用途/url/key/温度/上下文/参数(top_p/max_tokens…) |
| EmbeddingRebuildAlert | components/EmbeddingRebuildAlert.ts | 切换 Embedding 默认时弹「需重建向量索引」确认 |
| ScenePanel | components/ScenePanel.vue | 场景预设列表 + 编辑（名称/描述/chunk_size/top_k/system_prompt） |

## 3. 数据模型（types/settings.ts，来自原型 PROV/MGROUPS/MODELS）
```ts
type ModelGroup = 'llm'|'embed'|'rerank'
interface ModelDef { name:string; prov:string; use:string; temp?:number; ctx?:string;
  dim?:string; def?:boolean; url?:string; key?:string; params:Record<string,string> }
interface Scene { id:string; name:string; description:string; config:{chunk_size:number;top_k:number;system_prompt:string} }
```
供应商清单 PROV：DashScope / OpenAI 兼容 / 本地 Ollama / Azure OpenAI / 自建 vLLM。
用途按分组：LLM(答疑生成/快速摘要/问题改写)、Embedding(向量召回)、Rerank(精排)。

## 4. Store（stores/settings.ts）
```ts
state:{ models:Record<ModelGroup,ModelDef[]>, scenes:Scene[] }
actions:{ loadModels(), saveModel(g, m), setDefault(g, name), deleteModel(g, name),
  loadScenes(), saveScene(s), deleteScene(id) }
```

## 5. Mock（mock/settings.ts）：原型 MODELS（三组：qwen2.5-72b/7b/gpt-4o-mini；bge-m3/text-embedding-v3；bge-reranker-v2-m3/gte-rerank-v2）+ 场景(general/bid_doc)。

## 6. 实现步骤
1. 类型 + Store + Mock。2. 左侧导航 + 三组面板。3. 模型表格 + 配置弹窗 + 设默认。4. Embedding 切换重建提示。5. 场景面板 CRUD。

## 7. 验收
- [ ] 三组模型 CRUD，可设默认（同组单选默认）。
- [ ] 供应商/用途下拉联动；key 掩码。
- [ ] 切换 Embedding 默认 → 重建索引确认。
- [ ] 场景预设增删改。