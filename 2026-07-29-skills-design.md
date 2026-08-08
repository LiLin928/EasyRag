# Skill（技能）功能设计 Spec

| | |
|---|---|
| 日期 | 2026-07-29 |
| 状态 | 设计已确认（7 段），待 spec 审阅 → writing-plans |
| 交付物 | `frontend-prototype/index.html`（原型实现）+ 后端实现依据 |
| 关联 | `新版RAG需求设计文档_V2.md` · `docs/superpowers/specs/2026-07-29-frontend-pages-design.md` |
| 讨论方式 | superpowers:brainstorming，分段逐段确认 |

---

## 1. 背景与目标

**用户诉求**：「增加 skill 设置，并在 agent 中可以选择使用 skill，前后端应该怎么处理设置」。

**Skill 定义**：教智能体「怎么干」的复合能力包 —— 将**提示词 + 工具/知识库/工作流引用 + 示例**声明式打包，可选附带可执行脚本（二期投影为 Python 沙箱虚拟工具）。

**非目标（YAGNI）**：
- 不做插件框架（与 V2 文档决策 #12 一致）
- 技能不引用技能（天然无环）
- 技能不携带模型参数
- 一期不做自动路由（trigger 仅描述性）

## 2. 关键决策

| # | 决策 |
|---|---|
| D1 | **方案 C · 分层混合**：声明式复合能力包 + 可选 `scripts[]`；脚本复用既有 Python 工具沙箱通道，零新运行时 |
| D2 | **硬边界 ①**：技能不携带模型参数（model / temperature / max_tokens），agent 为唯一事实来源 |
| D3 | **硬边界 ②**：按 ID 引用，软失效，不级联删除 |
| D4 | **合并语义**：prompt = agent.prompt + Σ`## 技能：<name>\n`+S.prompt（按绑定序）；工具 = 并集去重 + `skill:<sid>:<fn>` 命名空间虚拟工具；docs/wfs 并集 |
| D5 | **披露**：一期全量注入（保存校验 ≤ skill_budget，默认 8k 字符）；二期可选渐进披露元工具 `load_skill(id)` |
| D6 | **分期**：一期 = 声明式全套（FE+BE）；二期 = scripts 投影 + 渐进披露 |

## 3. 构成（五组成）

| 组成 | 字段 | 说明 |
|---|---|---|
| ① meta | name / description / trigger / scope / version / icon | scope ∈ builtin\|custom；builtin 为只读种子数据 |
| ② prompt | prompt | 指令正文，技能核心 |
| ③ 引用 | tool_ids[] / doc_ids[] / wf_ids[] | 按 ID 软引用（原型中 wfs 按名称） |
| ④ 示例 | examples:[{q,a}] | few-shot，随技能块内联渲染 |
| ⑤ 脚本 | scripts:[{name,desc,params,code}] | **二期**，投影为虚拟工具 |

## 4. UI 设计

### 4.1 导航与路由
- 左侧导航「🧩 技能」插在 工具 与 MCP 之间
- 路由 `#/skills`；`ROUTES` 数组追加 `'skills'`

### 4.2 页头
- 副描述：教智能体「怎么干」的复合能力包
- 筛选 segment：全部 / 内置 / 自定义 / 可执行
- 搜索框 + 「新建技能」按钮

### 4.3 技能卡片
- trigger 独立一行，斜体灰字
- 构成 chips：🧩词数 / 🔧×N / 📚×N / ⚡×N / ▶可执行（amber 呼吸边）
- 反查：「已挂载 N 个智能体」
- 引用失效：⚠ chip

### 4.4 配置抽屉（双 Tab）
- **T1 基础**：名称 / 描述 / 触发时机 / 提示词 textarea + 字数 + 预算进度条（超 8k 红、禁存）/ 示例动态行
- 底部折叠：「高级 · 附带脚本（二期）」灰罩禁用
- **T2 引用**：工具 / 知识库 / 工作流 3 组勾选，复用既有 `ckRow(list,sel,key,nm,sub)`

### 4.5 三处联动
1. **Agent 卡片**：能力 chips 4→5 组（加 🧩 技能）
2. **Agent 装配抽屉**：第 5 组技能勾选；保存 toast「技能将自动带入其推荐工具」（告知不阻断）
3. **设置页**：「技能设置」分区 —— 预算滑块 4096–16384 + 渐进披露开关（二期，置灰）

### 4.6 演示数据（4 条）

| id | icon | name | scope | 关键引用 | 挂载 |
|---|---|---|---|---|---|
| sk1 | 📋 | 标书资质审查 SOP | builtin | t2 / d1 / wf「标书资质分析流程」 | a1 |
| sk2 | 📝 | 合同风险审查清单 | builtin | d2 | — |
| sk3 | 📊 | 研报摘要规范 | builtin | examples×2 | a2 |
| sk4 | 🧑‍💻 | 客服升级流程 | custom | t3 + scripts×1（二期预览） | a1 |

## 5. 数据模型

### 5.1 原型演示数据

```js
var SKILLS=[
  {id:'sk1', ico:'📋', name:'标书资质审查 SOP', scope:'builtin', ver:'v1.2',
   trigger:'当用户上传招标文件、或要求审查标书资质时',
   prompt:'按以下 SOP 执行：①提取资质要求清单 ②逐项比对营业执照/资质证书 ③输出《资质审查报告》并标注缺失项',
   tools:['t2'], docs:['d1'], wfs:['标书资质分析流程'],  // wfs 按名称引用（现有 WFS 无 id 字段）
   examples:[{q:'帮我审查这份招标文件的资质要求', a:'好的，我将按 SOP 三步执行…'}],
   scripts:[] },   // 二期字段；sk4 含 1 条仅作「高级·附带脚本」灰罩预览，一期不投影不执行
  // sk2 / sk3 / sk4 见 4.6 表
];
```

- `AGENTS` 每条追加 `skills:[]`（位于 `mcps` 之后）：a1→`['sk1','sk4']`，a2→`['sk3']`，a3→`[]`
- 卡片反查「已挂载 N」运行时遍历 AGENTS 计算，不落地字段

### 5.2 后端表结构

```sql
CREATE TABLE skills (
  id           BIGSERIAL PRIMARY KEY,
  tenant_id    BIGINT NOT NULL,
  name         VARCHAR(64)  NOT NULL,
  icon         VARCHAR(16)  NOT NULL DEFAULT '🧩',
  description  VARCHAR(512) NOT NULL DEFAULT '',
  trigger_text VARCHAR(200) NOT NULL DEFAULT '',
  scope        VARCHAR(16)  NOT NULL DEFAULT 'custom'
               CHECK (scope IN ('builtin','custom')),
  version      VARCHAR(16)  NOT NULL DEFAULT '1.0',
  prompt       TEXT         NOT NULL,
  tool_ids     BIGINT[] NOT NULL DEFAULT '{}',
  doc_ids      BIGINT[] NOT NULL DEFAULT '{}',
  wf_ids       BIGINT[] NOT NULL DEFAULT '{}',
  examples     JSONB    NOT NULL DEFAULT '[]',
  scripts      JSONB    NOT NULL DEFAULT '[]',
  created_by   BIGINT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name)
);
CREATE INDEX idx_skills_tenant ON skills(tenant_id);
ALTER TABLE agents ADD COLUMN skill_ids BIGINT[] NOT NULL DEFAULT '{}';
```

### 5.3 引用完整性（软失效不级联）

| 场景 | 规则 |
|---|---|
| 技能引用工具/知识库/工作流 | 不建 FK；读时解析；缺失 id 过滤并标记 `missing`，FE 显示 ⚠ |
| 引用的工具/文档被删 | 技能不级联、不阻塞，仅出现失效标记 |
| 删除技能 | 确认框提示「已挂载 N 个智能体」；删除后 agents 中 stale id 运行时静默跳过，下次保存 agent 时清理 |
| builtin 技能 | migration 种子数据，只读（隐藏删除/改名），仅可决定是否挂载 |

### 5.4 校验约束（前后端共用）

- `name` 必填 ≤64，租户内唯一；`prompt` 必填 ≤ `skill_budget`
- `trigger_text` ≤200；`description` ≤512
- `examples` ≤10 条（q≤200 / a≤1000）；三个引用数组各 ≤20 项
- `scripts`（二期）：≤5 个，单个 code ≤16KB，name 匹配 `^[a-z][a-z0-9_]{2,31}$`

### 5.5 系统设置新增

| key | 类型 | 默认 | 说明 |
|---|---|---|---|
| `skill_budget` | INT | 8192 | 4096–16384，对应设置页滑块 |
| `skill_progressive_disclosure` | BOOL | false | 二期，UI 先置灰 |

---

## 6. 后端 API

### 6.1 端点一览（`/api/v1`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/skills?scope=&q=&executable=&page=&size=` | 列表；返回含 `mounted_by`、`missing_refs` |
| GET | `/skills/:id` | 详情（含解析后的引用对象摘要） |
| POST | `/skills` | 创建（scope 强制 `custom`，version 默认 `1.0`） |
| PUT | `/skills/:id` | 更新；builtin → 403 |
| DELETE | `/skills/:id` | 删除；builtin → 403；**不级联**改 agents |
| GET | `/skills/:id/agents` | 反查：挂载该技能的智能体列表（供删除确认框） |
| PUT | `/agents/:id` | body 增加 `skill_ids`；响应回带解析结果 |

### 6.2 典型报文

**POST /skills** 请求：
```json
{ "name":"标书资质审查 SOP", "icon":"📋",
  "trigger_text":"当用户上传招标文件时",
  "prompt":"按以下 SOP 执行…",
  "tool_ids":[2], "doc_ids":[1], "wf_ids":[3],
  "examples":[{"q":"…","a":"…"}], "scripts":[] }
```

**响应 201**：完整对象 + `id` / `scope:"custom"` / `created_at`，并附：
```json
"warnings":[ {"type":"tool_missing","id":9} ]
```

**GET /skills 列表项**：
```json
{ "id":1, "name":"…", "scope":"builtin", "trigger_text":"…",
  "mounted_by":2, "missing_refs":["tool:9"], "executable":false }
```

### 6.3 校验流程（前后端共用规则）

```
POST/PUT → validateSkill(dto, settings)
  ├─ 结构/长度校验（5.4 节约束）
  ├─ prompt.length ≤ settings.skill_budget
  ├─ name 唯一性（tenant 内）→ 冲突 409
  └─ 引用解析：tool/doc/wf ids 逐个查存在性
        缺失 → 收集进 warnings（不报错，软失效）
```

### 6.4 错误码

| HTTP | code | 触发 |
|---|---|---|
| 400 | `VALIDATION` | 字段级错误，`fields:{prompt:"超出预算 8192（当前 9012）"}` |
| 403 | `FORBIDDEN` | 改/删 builtin 技能 |
| 404 | `NOT_FOUND` | id 不存在 |
| 409 | `CONFLICT` | 名称重复 |

### 6.5 Agent 侧联动

- `PUT /agents/:id` 接收 `skill_ids`；保存时过滤不存在的 skill id（静默）
- 响应附 `effective` 预览摘要：`{merged_prompt_len, tool_union:[…], skill_count}`，供抽屉即时显示「合并后提示词 N 字符」

## 7. 运行时合并

### 7.1 合并入口（每次会话启动执行一次）

```python
def build_effective(agent, settings):
    skills = [s for s in resolve(agent.skill_ids) if s]  # 过滤失效，保持绑定序
    return {
        "prompt": merge_prompt(agent, skills),
        "tools":  merge_tools(agent, skills),
        "doc_ids": ordered_unique(agent.doc_ids + flat(s.doc_ids for s in skills)),
        "wf_ids":  ordered_unique(agent.wf_ids  + flat(s.wf_ids  for s in skills)),
        "model_cfg": agent.{model,temp,maxtok},   # 硬边界：技能不携带模型参数
    }
```

### 7.2 三条合并规则

**① 提示词**（按 `skill_ids` 绑定序追加）：
```
{agent.prompt}

## 技能：标书资质审查 SOP
{skill.prompt}
示例：
Q: 帮我审查这份招标文件的资质要求
A: 好的，我将按 SOP 三步执行…
```
- examples 渲染为 few-shot，随技能块内联

**② 工具**：`ordered_unique(agent.tools + Σ skill.tools)`，agent 自有的在先；去重按 id

**③ 知识库 / 工作流**：同样并集去重

### 7.3 脚本投影（二期）

```
skill.scripts: [{name:"calc_penalty", params:[{n:"amount",t:"number"}], code:"def …"}]
        ↓ 投影
VirtualTool{
  name: "skill:4:calc_penalty",        # 命名空间隔离，绝不与 agent 自有工具撞名
  parameters: JSONSchema(from params),
  executor: PythonSandbox(code)        # 复用现有 Python 工具同款沙箱通道
}
```
沙箱边界沿用现有 Python 工具：无网络 / 无文件系统 / CPU 5s / 内存上限，**零新运行时**。

### 7.4 披露模式

| 期 | 模式 | 行为 |
|---|---|---|
| 一期 | **全量注入** | 全部技能 prompt 拼入系统提示；保存时校验合并后 ≤ skill_budget |
| 二期 | 渐进披露（可选） | 仅注入技能 meta（name+trigger）+ 元工具 `load_skill(id)`，模型按需拉取全文 |

### 7.5 兜底与边界

- **超长 backstop**：保存时已校验；运行时若仍超模型上下文 → 拒绝执行并报错「请减少挂载技能」
- **trigger_text 一期仅作描述**：展示于卡片/抽屉，不做自动路由
- **失效引用**：skill 内 missing 的工具/文档在合并时跳过，计入本次会话 warnings 日志

## 8. 错误处理与边界

### 8.1 保存时 —— 阻断性错误（400/409）

| 校验 | FE 即时反馈 |
|---|---|
| name 空 / >64 / 租户内重名 | 输入框红边 + 行内报错；重名提示「已存在同名技能」 |
| prompt 空 | 保存按钮禁用 + 提示 |
| prompt 超 skill_budget | 预算进度条 **≤80% navy → >80% amber → 超限 red**，保存禁用 |
| examples >10 条 / q>200 / a>1000 | 对应动态行标红 |
| scripts（二期）name 撞名、code>16KB、>5 个 | 脚本编辑区报错 |

### 8.2 运行时 —— 非阻断降级（软失效）

| 场景 | 行为 | 用户可见 |
|---|---|---|
| 技能引用的工具/文档/工作流已删 | 合并时跳过，写入会话 warnings | 卡片 ⚠ chip + 抽屉内「引用的 XX 已不存在」 |
| 技能已删（agent 持 stale id） | 静默跳过 | 下次保存 agent 时清理 |
| 脚本执行失败/超时（二期） | 错误串作为 tool result 交还模型自行处理；5s 强杀 | 对话内工具调用显示 ❌ 详情 |
| 合并后超模型上下文 | **拒绝启动会话** | toast 错误「合并提示词超限，请减少挂载技能」 |

### 8.3 并发与快照

- **会话启动即快照**：resolve 后冻结技能内容，会话中途编辑不影响进行中的会话
- 多人同改同一技能：last-write-wins + `updated_at`，不做乐观锁（YAGNI）

### 8.4 结构性边界（设计即免疫）

- 技能**不引用技能** → 天然无环、无递归披露问题
- 技能**不携带模型参数** → agent 是唯一事实来源，无合并冲突
- `skill_ids` 保存时去重 → 重复挂载无效
- builtin 只读 → 无「改坏内置技能」风险；自定义技能不提供 on/off 开关（挂载即生效，不挂即不用）

### 8.5 原型 FE 展示映射

- 抽屉：字段级实时校验（红边 + 行内文案）
- 删除：确认模态显示反查「已挂载 N 个智能体，删除后将自动解除」
- 统一 `toast(type, msg)`：成功绿 / 失败红 / 警告黄

## 9. 验证与测试

### 9.1 原型自动化校验（node 脚本落盘 `.cjs` 再跑）

| # | 检查项 | 通过标准 |
|---|---|---|
| 1 | 语法自检 | 全量内联脚本 `new Function` 无异常 |
| 2 | 路由 | `ROUTES` 含 `'skills'`；`#/skills` 渲染页面且 nav 高亮 |
| 3 | 数据完整 | `SKILLS` 4 条字段齐全；`a1.skills=['sk1','sk4']`、`a2=['sk3']`、`a3=[]` |
| 4 | 交叉引用 | 技能引用的 tool/doc id 存在于 TOOLS/DOCS；wfs 名称存在于 WFS |
| 5 | 卡片渲染 | chips（🧩词数 / 🔧×N / 📚×N / ⚡×N / ▶可执行）+ 反查「已挂载 N」正确 |
| 6 | 抽屉 | 双 Tab 切换；预算条 >8k 转红且禁存；示例行动态增删 |
| 7 | 三处联动 | agent 卡片 chips 5 组；装配抽屉第 5 组勾选；设置页「技能设置」分区存在 |
| 8 | 回归 | 既有 11 页面全部可达（不破坏 Round 5 路由修复） |

### 9.2 手工验收清单

- [ ] 新建技能（含示例 2 条）→ 保存 toast → 列表出现
- [ ] 挂载 sk1 到 agent → 保存 toast「技能将自动带入其推荐工具」→ 卡片 chips 更新
- [ ] 删 t2 → sk1 卡片出现 ⚠ chip，抽屉显示失效说明
- [ ] 删 sk1 → 确认框「已挂载 1 个智能体」→ 删后 a1 chips 回落
- [ ] 预算滑块（设置页）调到 4k → 抽屉进度条阈值联动

### 9.3 后端测试用例（spec 级，供后续实现）

- **单元**：`validateSkill` 预算边界（8192 过 / 8193 拒）、重名 409、builtin 改写 403；`merge_prompt` 绑定序 + examples 渲染；`ordered_unique` 保序去重；脚本投影命名空间 `skill:4:calc_penalty`
- **集成**：POST→GET 回环；DELETE 后反查与 agent 清理；软失效 `missing_refs` 返回
- **E2E**：`build_effective` 会话快照隔离（会话中改技能不影响进行中会话）

### 9.4 验收标准（DoD）

自动化 8 项全 PASS + 手工清单全 ✓ + spec 自审/用户审通过 → 进入 writing-plans。

## 10. 分期计划

| 期 | 范围 |
|---|---|
| **一期**（本轮） | 技能页 + 抽屉 + 演示数据；agent 联动（卡片/装配/toast）；设置页技能设置分区；声明式后端 API 全套 spec |
| **二期** | scripts 投影（Python 沙箱虚拟工具）；渐进披露 `load_skill(id)`；设置开关启用 |

## 11. 未决项

无 —— 7 段设计已全部确认。