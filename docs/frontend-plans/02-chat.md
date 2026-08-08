# 02 · 智能对话 Chat

> 原型页面：page-chat。最复杂模块：SSE 流式回答、四阶段指示器、分级引用、文档选择、结构树联动。

## 1. 目标

三栏布局对话页：左会话列表 / 中对话区（流式 Markdown + 引用 + 阶段指示器 + 输入框）/ 右文档选择器 + 结构树。

## 2. SSE 事件（设计文档 7.2.3）

POST /chat（`text/event-stream`），事件顺序：
```
phase(parse) → phase(navigate) → navigation(anchors)
→ phase(retrieve) → references([]) → phase(generate)
→ token(...) 逐个 → done(message_id,usage) → trace(nav/retrieve/generate ms)
```
错误：`event:error data:{code,message}`。

## 3. 组件清单（views/chat/）

| 组件 | 路径 | 职责 |
|------|------|------|
| ChatView | ChatView.vue | 三栏容器，管理会话与流 |
| ConversationList | components/ConversationList.vue | 左栏会话列表，新建/删除/切换 |
| MessageList | components/MessageList.vue | 消息流容器，自动滚到底 |
| ChatMessage | components/ChatMessage.vue | 单条消息（区分 user/assistant） |
| PhaseIndicator | components/PhaseIndicator.vue | 四阶段进度（解析→导航→检索→生成），当前阶段高亮 |
| StreamRenderer | components/StreamRenderer.ts | 逐 token 追加 + Markdown(marked)+高亮+DOMPurify |
| ReferenceList | components/ReferenceList.vue | 引用列表容器（折叠态） |
| ReferenceCard | components/ReferenceCard.vue | 单引用卡：[n] 文档 p页 / 章节 / 80字预览 |
| ReferenceDetail | components/ReferenceDetail.ts | 展开态：调 GET /elements/{id} 取全文 + 上下文按钮 |
| ChatInput | components/ChatInput.vue | 输入框（自适应高） + 发送，Enter 发送/Shift+Enter 换行 |
| DocumentPicker | components/DocumentPicker.vue | 右栏文档多选（从知识库取），全选/清空 |
| TreeBrowser | （复用 03 组件） | 右栏结构树浏览，与引用联动高亮 |
| SceneSelector | components/SceneSelector.vue | 顶栏场景切换下拉（复用，也可放顶栏） |

## 4. 数据模型（types/chat.ts）

```ts
interface Conversation { id:string; title:string; lastTime:string; msgCount:number }
interface ChatMessage { id:string; role:'user'|'assistant'; content:string;
  references?:Reference[]; phase?:Phase; trace?:TraceInfo; usage?:Usage; ts:string }
type Phase = 'idle'|'parse'|'navigate'|'retrieve'|'generate'
interface Reference { ref_id:string; element_id:string; doc_title:string;
  node_title:string; content_preview:string; score:number; type:'text'|'table'|'image' }
interface TraceInfo { trace_id:string; nav_ms:number; retrieve_ms:number; generate_ms:number; total_ms:number }
```

## 5. Store（stores/chat.ts）

```ts
state: {
  conversations:[], activeConversationId, messages:[],
  isStreaming:false, currentPhase:'idle', streamBuffer:'',
  references:[], traceInfo:null,
  selectedDocIds:[], activeScene:'general'
}
actions: {
  sendMessage(question)   // 建 useSSE，按事件更新上面字段；done 时 finalizeMessage
  createConversation(), deleteConversation(id), loadHistory(convId)
  setSelectedDocs(ids), setScene(scene)
}
```

## 6. 分级引用交互（设计文档 8.7）

- L0 内联：回答中 `[1][2]` 上标，点击滚动到对应引用卡。
- L1 卡片：回答下方折叠列表（文档名+章节+80字预览）。
- L2 详情：点卡片展开 → `GET /elements/{id}` 取全文（表格渲染 HTML table，图片缩略图可放大）。
- L3 上下文：「查看上下文」→ `GET /elements/{id}/context?window=3` 取前后兄弟。

## 7. 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /chat | SSE 对话 |
| GET/POST | /chat/conversations[/:id] | 会话列表/创建 |
| GET | /chat/conversations/{id}/messages | 历史 |
| DELETE | /chat/conversations/{id} | 删除会话 |
| GET | /elements/{id} | 元素详情（引用懒加载） |
| GET | /elements/{id}/context | 上下文 |
| GET | /scenes | 场景列表 |
| POST | /feedback | 👍/👎 |

## 8. Mock（mock/chat.ts）

- 会话列表（原型 CONVS）；历史消息（user/assistant 各一条）。
- SSE 模拟器：用定时器按顺序 emit phase/navigation/references/token（逐 token 喂一段标书分析回答），done/trace。可用一个模拟回答文本数组逐字推送。
- 引用 mock（原型 REFS：含 text/table 两种）。

## 9. 实现步骤

1. 类型 + chatStore + useSSE 接入 + Mock SSE。
2. 三栏骨架 + ConversationList + 切换。
3. MessageList + ChatMessage + PhaseIndicator。
4. StreamRenderer（Markdown 流式渲染）。
5. ReferenceList/Card/Detail（分级引用 + 懒加载 + 上下文）。
6. DocumentPicker + TreeBrowser（联动知识库）。
7. ChatInput + 场景选择 + 反馈。

## 10. 验收

- [ ] 发送问题 → 阶段指示器依次点亮 → token 流式逐字渲染 → done 收尾。
- [ ] 引用卡片折叠/展开，展开懒加载全文，表格渲染为表。
- [ ] 切换会话加载历史；新建/删除会话。
- [ ] 文档选择影响「基于已选 N 篇」提示；结构与引用联动高亮。
- [ ] 底部状态栏显示 nav/retrieve/generate/total 耗时。