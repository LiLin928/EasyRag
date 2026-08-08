# 10 · 待办中心 Todos

> 原型页面：page-todos。工作流「人工介入」节点产生的待办，含动态表单与超时倒计时。

## 1. 目标

全局待办列表（待处理/已完成）；点击展开详情；根据表单 schema 动态渲染表单；提交回写工作流；超时倒计时。

## 2. 组件清单（views/todos/）

| 组件 | 路径 | 职责 |
|------|------|------|
| TodosView | TodosView.vue | 容器 + 列表（待处理/已完成 分组或 Tab） |
| TodoItem | components/TodoItem.vue | 待办条：标题 + 来源(流程·节点) + 状态徽标 + 倒计时(待处理)/处理时间(已完成) |
| TodoDetail | components/TodoDetail.vue | 右侧/展开详情：流程信息 + 动态表单 + 提交/驳回按钮 + 超时提示 |
| DynamicForm | components/DynamicForm.vue | 据 schema 渲染 el-form（text/textarea/select/radio/number/upload），校验后输出 |
| CountdownBadge | components/CountdownBadge.vue | 剩余时间倒计时（HH:MM:SS），到时灰显「已超时」 |

## 3. 数据模型（types/todo.ts，设计文档 9.2）
```ts
interface Todo { id:string; title:string; source:string;   // 流程 · human_1
  status:'pending'|'done'|'rejected'; submittedAt?:string;
  cd?:boolean; deadline?:number;                            // 秒级剩余
  formSchema:FormField[]; formData?:Record<string,any> }
interface FormField { key:string; label:string; type:'text'|'textarea'|'select'|'radio'|'number'|'upload';
  required?:boolean; options?:{label:string;value:string}[] }
```

## 4. Store（stores/todo.ts）
```ts
state:{ todos:[], activeTodoId }
actions:{ loadTodos(), loadTodo(id), submitTodo(id, formData), rejectTodo(id), tickCountdown() }
```
倒计时：app 启动一个全局 `setInterval` 每秒 `tickCountdown()`。

## 5. 接口（设计文档 12.1）
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /todos | 待办列表（?status=） |
| GET | /todos/{id} | 详情（含 formSchema） |
| POST | /todos/{id}/submit | 提交表单 → 触发工作流 execution_resumed |

## 6. Mock（mock/todo.ts）：原型 TODOS（标书资质分析待审批 + 已处理项），含 formSchema（如「审批意见 textarea + 通过/驳回 radio」），倒计时从 23:41:52 递减。

## 7. 实现步骤
1. 类型 + Store + Mock + 全局倒计时。2. 列表 + 详情切换。3. DynamicForm 按 schema 渲染。4. 提交/驳回 → 状态流转。

## 8. 验收
- [ ] 待办列表分待处理/已完成；倒计时每秒刷新，到时灰显。
- [ ] 动态表单按 schema 渲染并校验；提交后转已完成并显示处理时间。
- [ ] 提交回写工作流（Mock 触发 resumed 事件）。